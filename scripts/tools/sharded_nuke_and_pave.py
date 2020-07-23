#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Issues sharded subordinatekill, delete build directory, and reboot commands."""

import multiprocessing
import optparse
import os
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common import chromium_utils
from main import subordinates_list


def get_mains(parser, options):
  """Given parser options, find suitable main directories."""
  paths = []
  mains_path = chromium_utils.ListMains()

  # Populates by defaults with every mains with a twistd.pid, thus has
  # been started.
  if not options.main:
    for m_p in mains_path:
      if  os.path.isfile(os.path.join(m_p, 'twistd.pid')):
        paths.append(m_p)
  elif options.main == 'all':
    paths.extend(mains_path)
  elif options.main in (os.path.basename(p) for p in mains_path):
    full_main = next(
        p for p in mains_path if os.path.basename(p) == options.main)
    paths.append(full_main)
  else:
    parser.error('Unknown main \'%s\'.\nChoices are:\n  %s' % (
        options.main, '\n  '.join((
            os.path.basename(p) for p in mains_path))))
  return paths


def get_subordinates(main_paths, subordinatelist):
  """Return subordinates split up by OS.

  Takes a list of main paths and an optional subordinate whitelist."""

  subordinatedict = {}
  for path in main_paths:
    for subordinate in chromium_utils.GetSubordinatesFromMainPath(path):
      if 'hostname' in subordinate:
        subordinatedict[subordinate['hostname']] = subordinate
  subordinates = subordinates_list.BaseSubordinatesList(subordinatedict.values())
  def F(os_type):
    out = subordinates.GetSubordinates(os=os_type)
    named_subordinates = [s.get('hostname') for s in out]

    if subordinatelist:
      return [s for s in named_subordinates if s in subordinatelist]
    else:
      return named_subordinates

  subordinate_dict = {}
  subordinate_dict['win'] = list(set(F('win')))
  subordinate_dict['linux'] = list(set(F('linux')))
  subordinate_dict['mac'] = list(set(F('mac')))

  return subordinate_dict


def get_commands(subordinates):
  """Depending on OS, yield the proper nuke-and-pave command sequence."""
  commands = {}
  for subordinate in subordinates['win']:
    def cmd(command):
      return 'cmd.exe /c "%s"' % command
    def cygwin(command):
      return 'c:\\cygwin\\bin\\bash --login -c "%s"' % (
          command.replace('"', '\\"'))

    commands[subordinate] = [
        cmd('taskkill /IM python.exe /F'),
        cygwin('sleep 3'),
        cygwin('rm -r -f /cygdrive/e/b/build/subordinate/*/build'),
        cmd('shutdown -r -f -t 1'),
    ]

  for subordinate in subordinates['mac'] + subordinates['linux']:
    commands[subordinate] = [
        'make -C /b/build/subordinate stop',
        'sleep 3',
        'rm -rf /b/build/subordinate/*/build',
        'sudo shutdown -r now',
    ]
  return commands


def status_writer(queue):
  # Send None to kill the status writer.
  msg = queue.get()
  while msg:
    print '\n'.join(msg)
    msg = queue.get()


def stdout_writer(queue):
  # Send None to kill the stdout writer.
  subordinate = queue.get()
  while subordinate:
    print '%s: finished' % subordinate
    subordinate = queue.get()


def journal_writer(filename, queue):
  # Send None to kill the journal writer.
  with open(filename, 'a') as f:
    subordinate = queue.get()
    while subordinate:
      # pylint: disable=C0323
      print >>f, subordinate
      subordinate = queue.get()


def shard_subordinates(subordinates, max_per_shard):
  """Shart subordinates with no more than max_per_shard in each shard."""
  shards = []
  for i in xrange(0, len(subordinates), max_per_shard):
    shards.append(list(subordinates.iteritems())[i:i+max_per_shard])
  return shards


def run_ssh_command(subordinatepair, worklog, status, errorlog, options):
  """Execute an ssh command as chrome-bot."""
  subordinate, commands = subordinatepair
  needs_connect = subordinate.endswith('-c4')
  if options.corp:
    subordinate = subordinate + '.chrome'

  if needs_connect:
    ssh = ['connect', subordinate, '-r']
  else:
    identity = ['chrome-bot@%s' % subordinate]
    ssh = ['ssh', '-o ConnectTimeout=5'] + identity
  if options.dry_run:
    for command in commands:
      status.put(['%s: %s' % (subordinate, command)])
    return

  retcode = 0
  for command in commands:
    status.put(['%s: %s' % (subordinate, command)])
    retcode = subprocess.call(ssh + [command])
    if options.verbose:
      status.put(['%s: previous command returned code %d' % (subordinate, retcode)])
    if retcode != 0 and command != commands[0]:  # Don't fail on subordinatekill.
      break

  if retcode == 0:
    worklog.put(subordinate)
  else:
    errorlog.put(subordinate)


class Worker(object):
  def __init__(self, out_queue, status, errorlog, options):
    self.out_queue = out_queue
    self.status = status
    self.options = options
    self.errorlog = errorlog
  def __call__(self, subordinate):
    run_ssh_command(subordinate, self.out_queue, self.status, self.errorlog,
                    self.options)


def main():
  usage = '%prog [options]'
  parser = optparse.OptionParser(usage=usage)
  parser.add_option('--main',
      help=('Main to use to load the subordinates list. If omitted, all mains '
            'that were started at least once are included. If \'all\', all '
            'mains are selected.'))
  parser.add_option('--subordinatelist',
      help=('List of subordinates to contact, separated by newlines.'))
  parser.add_option('--max-per-shard', default=50,
      help=('Each shard has no more than max-per-shard subordinates.'))
  parser.add_option('--max-connections', default=16,
      help=('Maximum concurrent SSH sessions.'))
  parser.add_option('--journal',
      help=('Log completed subordinates to a journal file, skipping them'
            'on the next run.'))
  parser.add_option('--errorlog',
      help='Log failed subordinates to a file instead out stdout.')
  parser.add_option('--dry-run', action='store_true',
      help='Don\'t execute commands, only print them.')
  parser.add_option('--corp', action='store_true',
      help='Connect to bots within the corp network.')
  parser.add_option('-v', '--verbose', action='store_true')
  options, _ = parser.parse_args(sys.argv)

  mains = get_mains(parser, options)
  if options.verbose:
    print 'reading from:'
    for main in mains:
      print '  ', main

  subordinatelist = []
  if options.subordinatelist:
    with open(options.subordinatelist) as f:
      subordinatelist = [s.strip() for s in f.readlines()]
  subordinates = get_subordinates(mains, subordinatelist)

  if options.verbose and options.subordinatelist:
    wanted_subordinates = set(subordinatelist)
    got_subordinates = set()
    for _, s in subordinates.iteritems():
      got_subordinates.update(s)

    diff = wanted_subordinates - got_subordinates
    if diff:
      print 'Following subordinates are not on selected mains:'
      for s in diff:
        print '  ', s

  if options.journal and os.path.exists(options.journal):
    skipped = set()
    with open(options.journal) as f:
      finished_subordinates = set([s.strip() for s in f.readlines()])
    for os_type in subordinates:
      skipped.update(set(subordinates[os_type]) & finished_subordinates)
      subordinates[os_type] = list(set(subordinates[os_type]) - finished_subordinates)
    if options.verbose:
      print 'Following subordinates have already been processed:'
      for s in skipped:
        print '  ', s

  commands = get_commands(subordinates)
  shards = shard_subordinates(commands, options.max_per_shard)
  pool = multiprocessing.Pool(processes=options.max_connections)
  m = multiprocessing.Manager()
  worklog = m.Queue()
  status = m.Queue()
  errors = m.Queue()

  # Set up the worklog and status writers.
  if options.journal:
    p = multiprocessing.Process(target=journal_writer,
                                args=(options.journal, worklog))
  else:
    p = multiprocessing.Process(target=stdout_writer, args=(worklog,))
  s = multiprocessing.Process(target=status_writer, args=(status,))

  p.start()
  s.start()

  # Execute commands.
  for shard in shards:
    if options.verbose:
      print 'Starting next shard with subordinates:'
      for subordinate in shard:
        print '  ', subordinate

    pool.map_async(Worker(worklog, status, errors, options), shard).get(9999999)
    raw_input('Shard finished, press enter to continue...')

  # Clean up the worklog and status writers.
  worklog.put(None)  # Signal worklog writer to stop.
  status.put(None)  # Signal status writer to stop.
  p.join()
  s.join()

  # Print out errors.
  error_list = []
  errors.put(None)  # Signal end of error list.
  e = errors.get()
  while e:
    error_list.append(e)
    e = errors.get()
  if error_list:
    if options.errorlog:
      with open(options.errorlog, 'w') as f:
        for error in error_list:
          # pylint: disable=C0323
          print >>f, error
    else:
      print 'Following subordinates had errors:'
      for error in error_list:
        print '  ', error

  return 0


if __name__ == '__main__':
  sys.exit(main())
