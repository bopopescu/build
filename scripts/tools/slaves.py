#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A small maintenance tool to do mass execution on the subordinates."""

import os
import optparse
import re
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common import chromium_utils
from main import subordinates_list


def SubRun(enabled, names, cmd, options):
  if enabled:
    if options.max:
      max_index = options.max
    else:
      max_index = len(names)
    if options.min:
      min_index = options.min
    else:
      min_index = 1
    for index in range(min_index, max_index + 1):
      host = names[index - 1]
      replacements = {
          'index': index,
          'host': host,
          'number': index,
      }
      m = re.match(r'^(mini|vm)(\d+)-.*', host)
      if m:
        replacements['number'] = m.group(2)
      command = [item % replacements for item in cmd]
      if not options.quiet:
        print "> %s" % " ".join(command)
      if not options.print_only:
        retcode = subprocess.call(command)
        if retcode:
          if not options.ignore_failure:
            print 'Stopped at index %d' % index
          if not options.quiet:
            print 'Returned %d' % retcode
          if not options.ignore_failure:
            return retcode
  return 0


def RunSSH(options):
  win_cmd = options.win_cmd
  if win_cmd:
    if options.no_cygwin:
      # prepend with cmd.exe /c so PATH is correctly searched.
      win_cmd = 'cmd.exe /c "%s"' % win_cmd
    else:
      # Wrap up in cygwin's bash.
      win_cmd = 'c:\\cygwin\\bin\\bash --login -c "%s"' % (
          win_cmd.replace('"', '\\"'))

  ssh = ['ssh', '-o ConnectTimeout=5']
  quiet = ['-q'] if options.quiet else []
  identity = ['chrome-bot@%(host)s']

  retcode = SubRun(options.win, options.win_names,
                   ssh + quiet + identity + [win_cmd], options)
  if not retcode:
    retcode = SubRun(options.linux, options.linux_names,
                     ssh + ['-t'] + quiet + identity + [options.linux_cmd],
                     options)
  if not retcode:
    retcode = SubRun(options.mac, options.mac_names,
                     ssh + ['-t'] + quiet + identity + [options.mac_cmd],
                     options)
  return retcode


def RunSCP(options, src, dst):
  cmd = ['scp', src, 'chrome-bot@%(host)s:' + dst]
  retcode = SubRun(options.win, options.win_names, cmd, options)
  if not retcode:
    retcode = SubRun(options.linux, options.linux_names, cmd, options)
  if not retcode:
    retcode = SubRun(options.mac, options.mac_names, cmd, options)
  return retcode


def Clobber(options):
  options.no_cygwin = False
  path_dbg = '/cygdrive/e/b/build/subordinate/*/build/src/*/Debug'
  path_rel = '/cygdrive/e/b/build/subordinate/*/build/src/*/Release'
  options.win_cmd = 'rm -rf %s %s' % (path_dbg, path_rel)
  path_ninja = '/b/build/subordinate/*/build/src/out'
  options.linux_cmd = 'rm -rf %s' % path_ninja
  path = '/b/build/subordinate/*/build/src/{xcodebuild,out}'
  options.mac_cmd = 'rm -rf %s' % path
  # We don't want to stop if one subordinate failed.
  options.ignore_failure = True
  return RunSSH(options)


def Revert(options):
  options.no_cygwin = False
  path = '/cygdrive/e/b/build/subordinate/*/build/src'
  options.win_cmd = r'cd %s && gclient.bat revert' % path
  path = '/b/build/subordinate/*/build/src'
  options.linux_cmd = 'cd %s && gclient revert' % path
  options.mac_cmd = 'cd %s && gclient revert' % path
  options.ignore_failure = True
  return RunSSH(options)


def Restart(options):
  options.no_cygwin = True
  options.win_cmd = 'shutdown -r -f -t 1'
  options.linux_cmd = 'sudo shutdown -r now'
  options.mac_cmd = 'sudo shutdown -r now'
  # We don't want to stop if one subordinate failed.
  options.ignore_failure = True
  return RunSSH(options)


def SyncScripts(options):
  options.no_cygwin = True
  options.win_cmd = 'cd /d E:\\b && depot_tools\\gclient sync'
  options.linux_cmd = 'cd /b && ./depot_tools/gclient sync'
  options.mac_cmd = 'cd /b && ./depot_tools/gclient sync'
  return RunSSH(options)


def TaskKill(options):
  options.no_cygwin = True
  options.win_cmd = 'taskkill /im crash_service.exe'
  options.ignore_failure = True
  options.win = True
  options.linux = False
  options.mac = False
  return RunSSH(options)


def InstallMsi(options):
  """Example."""
  options.no_cygwin = True
  options.win_cmd = 'msiexec /quiet /i \\\\hostname\\sharename\\appverif.msi'
  options.linux = False
  options.mac = False
  return RunSSH(options)


def ProcessShortName(main):
  """Substitutes shortcuts."""
  main = re.sub(r'\bt\b', 'tryserver', main)
  main = re.sub(r'\bc\b', 'chromium', main)
  return re.sub(r'\bco\b', 'chromiumos', main)


def Main(argv):
  usage = """%prog [options]

Sample usage:
  %prog -x t.c --index 5 -i -W "cmd rd /q /s c:\\b\\build\\subordinate\\win\\build"
  %prog -x chromium -l -c

Note: t is replaced with 'tryserver', 'c' with chromium' and
      co with 'chromiumos'."""

  # Generate the list of available mains.
  mains_path = chromium_utils.ListMains()
  mains = [os.path.basename(f) for f in mains_path]
  # Strip off 'main.'
  mains = [re.match(r'(main\.|)(.*)', m).group(2) for m in mains]
  parser = optparse.OptionParser(usage=usage)
  group = optparse.OptionGroup(parser, 'Subordinates to process')
  group.add_option('-x', '--main',
      help=('Main to use to load the subordinates list. If omitted, all mains '
            'that were started at least once are included. If \'all\', all '
            'mains are selected. Choices are: %s.') %
              ', '.join(mains))
  group.add_option('-w', '--win', action='store_true')
  group.add_option('-l', '--linux', action='store_true')
  group.add_option('-m', '--mac', action='store_true')
  group.add_option('--bits', help='Subordinate os bitness', type='int')
  group.add_option('--version', help='Subordinate os version')
  group.add_option('-b', '--builder',
                   help='Only subordinates attached to a specific builder')
  group.add_option('--min', type='int')
  group.add_option('--max', type='int', help='Inclusive')
  group.add_option('--index', type='int', help='execute on only one subordinate')
  group.add_option('-s', '--subordinate', action='append')
  group.add_option('--raw', help='Line separated list of subordinates to use. Must '
                                 'still use -l, -m or -w to let the script '
                                 'know what command to run')
  parser.add_option_group(group)
  parser.add_option('-i', '--ignore_failure', action='store_true',
                    help='Continue even if ssh returned an error')
  group = optparse.OptionGroup(parser, 'Premade commands')
  group.add_option('-c', '--clobber', action='store_true')
  group.add_option('-r', '--restart', action='store_true')
  group.add_option('--revert', action='store_true',
                   help='Execute gclient revert')
  group.add_option('--sync_scripts', action='store_true')
  group.add_option('--taskkill', action='store_true')
  group.add_option('--scp', action='store_true',
                   help='with the source and dest files')
  group.add_option('-q', '--quiet', action='store_true',
                   help='Quiet mode - do not print the commands')
  group.add_option('-p', '--print_only', action='store_true',
                   help='Print which subordinates would have been processed but do '
                        'nothing. With no command, just print the list of '
                        'subordinates for the given platform(s).')
  group.add_option('-N', '--no_cygwin', action='store_true',
                   help='By default cygwin\'s bash is called to execute the '
                        'command')
  parser.add_option_group(group)
  group = optparse.OptionGroup(parser, 'Custom commands')
  group.add_option('-W', '--win_cmd', help='Run a custom command instead')
  group.add_option('-L', '--linux_cmd')
  group.add_option('-M', '--mac_cmd')
  parser.add_option_group(group)
  options, args = parser.parse_args(argv)

  # If a command is specified, the corresponding platform is automatically
  # enabled.
  if options.linux_cmd:
    options.linux = True
  if options.mac_cmd:
    options.mac = True
  if options.win_cmd:
    options.win = True

  if options.raw:
    # Remove extra spaces and empty lines.
    options.subordinate = filter(None, (s.strip() for s in open(options.raw, 'r')))

  if not options.subordinate:
    if not options.main:
      # Populates by defaults with every mains with a twistd.pid, thus has
      # been started.
      subordinates = []
      for m_p in mains_path:
        if os.path.isfile(os.path.join(m_p, 'twistd.pid')):
          subordinates.extend(chromium_utils.GetSubordinatesFromMainPath(m_p))
      subordinates = subordinates_list.BaseSubordinatesList(subordinates)
    elif options.main == 'all':
      subordinates = []
      for m_p in mains_path:
        subordinates.extend(chromium_utils.GetSubordinatesFromMainPath(m_p))
      subordinates = subordinates_list.BaseSubordinatesList(subordinates)
    else:
      if not options.main in mains:
        options.main = ProcessShortName(options.main)
        if not options.main in mains:
          parser.error('Unknown main \'%s\'.\nChoices are: %s' % (
            options.main, ', '.join(mains)))
      main_path = mains_path[mains.index(options.main)]
      subordinates = chromium_utils.GetSubordinatesFromMainPath(main_path)
      subordinates = subordinates_list.BaseSubordinatesList(subordinates)
    def F(os_type):
      out = subordinates.GetSubordinates(os=os_type, bits=options.bits,
          version=options.version, builder=options.builder)
      # Skips subordinate without a hostname.
      return [s.get('hostname') for s in out if s.get('hostname')]
    options.win_names = F('win')
    options.linux_names = F('linux')
    options.mac_names = F('mac')
  else:
    subordinates = options.subordinate
    options.win_names = subordinates
    options.linux_names = subordinates
    options.mac_names = subordinates

  if not options.linux and not options.mac and not options.win:
    parser.print_help()
    return 0

  if options.index:
    options.min = options.index
    options.max = options.index

  if options.scp:
    if len(args) != 2:
      parser.error('Need 2 args')
    return RunSCP(options, args[0], args[1])
  if args:
    parser.error('Only --scp expects arguments')

  if options.restart:
    return Restart(options)
  elif options.clobber:
    return Clobber(options)
  elif options.sync_scripts:
    return SyncScripts(options)
  elif options.taskkill:
    return TaskKill(options)
  elif options.revert:
    return Revert(options)
  elif options.print_only and not (options.win_cmd or options.linux_cmd or
                                   options.mac_cmd):
    names_list = []
    if not options.min:
      options.min = 1
    if options.win:
      max_i = len(options.win_names)
      if options.max:
        max_i = options.max
      names_list += options.win_names[options.min - 1:max_i]
    if options.linux:
      max_i = len(options.linux_names)
      if options.max:
        max_i = options.max
      names_list += options.linux_names[options.min - 1:max_i]
    if options.mac:
      max_i = len(options.mac_names)
      if options.max:
        max_i = options.max
      names_list += options.mac_names[options.min - 1:max_i]
    print '\n'.join(names_list)
  else:
    if ((options.win and not options.win_cmd) or
        (options.linux and not options.linux_cmd) or
        (options.mac and not options.mac_cmd)):
      parser.error('Need to specify a command')
    return RunSSH(options)


if __name__ == '__main__':
  sys.exit(Main(None))
