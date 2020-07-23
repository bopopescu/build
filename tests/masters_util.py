# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Buildbot main utility functions.
"""

import json
import errno
import logging
import os
import sys
import time

BUILD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BUILD_DIR, 'scripts'))

from tools import mainmap
from common import find_depot_tools  # pylint: disable=W0611
import subprocess2


def sublists(superlist, n):
  """Breaks a list into list of sublists, each of length no more than n."""
  result = []
  for cut in range(0, len(superlist), n):
    result.append(superlist[cut:cut + n])
  return result


def pid_exists(pid):
  """Returns True if there is a process in the system with given |pid|."""
  try:
    os.kill(pid, 0)
  except OSError as error:
    if error.errno == errno.EPERM:
      return True
    elif error.errno == errno.ESRCH:
      return False
    raise
  return True


def is_main_alive(main, path):
  """Reads main's *.pid file and checks for corresponding PID in the system.
  If there is no such process, removes stale *.pid file and returns False.

  Returns:
    True - *.pid file exists and corresponding process is running.
    False - *.pid file doesn't exist or there is no such process.
  """
  pid_path = os.path.join(path, 'twistd.pid')
  contents = None
  try:
    with open(pid_path) as f:
      contents = f.read()
    if pid_exists(int(contents.strip())):
      return True
    logging.warning('Ghost twistd.pid for %s, removing it', main)
  except IOError as error:
    if error.errno == errno.ENOENT:
      return False
    raise
  except ValueError:
    logging.warning('Corrupted twistd.pid for %s, removing it: %r',
                    main, contents)
  remove_file(pid_path)
  return False


def remove_file(path):
  """Deletes file at given |path| if it exists. Does nothing if it's not there
  or can not be deleted."""
  try:
    os.remove(path)
  except OSError:
    pass


def start_main(main, path, dry_run=False):
  """Asynchronously starts the |main| at given |path|.
  If |dry_run| is True, will start the main in a limited mode suitable only
  for integration testing purposes.

  Returns:
    True - the main was successfully started.
    False - the main failed to start, details are in the log.
  """
  try:
    env = os.environ.copy()
    if dry_run:
      # Ask ChromiumGitPoller not to pull git repos.
      env['NO_REVISION_AUDIT'] = '0'
      env['POLLER_DRY_RUN'] = '1'
    subprocess2.check_output(
        ['make', 'start'], timeout=120, cwd=path, env=env,
        stderr=subprocess2.STDOUT)
  except subprocess2.CalledProcessError as e:
    logging.error('Error: cannot start %s' % main)
    print e
    return False
  return True


def stop_main(main, path, force=False):
  """Issues 'stop' command and waits for main to terminate. If |force| is True
  will try to kill main process if it fails to terminate in time by itself.

  Returns:
    True - main was stopped, killed or wasn't running.
    False - main is still running.
  """
  if terminate_main(main, path, 'stop', timeout=10):
    return True
  if not force:
    logging.warning('Main %s failed to stop in time', main)
    return False
  logging.warning('Main %s failed to stop in time, killing it', main)
  if terminate_main(main, path, 'kill', timeout=2):
    return True
  logging.warning('Main %s is still running', main)
  return False


def terminate_main(main, path, command, timeout=10):
  """Executes 'make |command|' and waits for main to stop running or until
  |timeout| seconds pass.

  Returns:
    True - the main was terminated or wasn't running.
    False - the command failed, or main failed to terminate in time.
  """
  if not is_main_alive(main, path):
    return True
  try:
    env = os.environ.copy()
    env['NO_REVISION_AUDIT'] = '0'
    subprocess2.check_output(
        ['make', command], timeout=5, cwd=path, env=env,
        stderr=subprocess2.STDOUT)
  except subprocess2.CalledProcessError as e:
    if not is_main_alive(main, path):
      return True
    logging.warning('Main %s was not terminated: \'make %s\' failed: %s',
                    main, command, e)
    return False
  return wait_for_termination(main, path, timeout=timeout)


def wait_for_termination(main, path, timeout=10):
  """Waits for main to finish running and cleans up pid file.
  Waits for at most |timeout| seconds.

  Returns:
    True - main has stopped or wasn't running.
    False - main failed to terminate in time.
  """
  started = time.time()
  while True:
    now = time.time()
    if now > started + timeout:
      break
    if not is_main_alive(main, path):
      logging.info('Main %s stopped in %.1f sec.', main, now - started)
      return True
    time.sleep(0.1)
  return False


def search_for_exceptions(path):
  """Looks in twistd.log for an exception.

  Returns True if an exception is found.
  """
  twistd_log = os.path.join(path, 'twistd.log')
  with open(twistd_log) as f:
    lines = f.readlines()
    stripped_lines = [l.strip() for l in lines]
    try:
      i = stripped_lines.index('--- <exception caught here> ---')
      # Found an exception at line 'i'!  Now find line 'j', the number
      # of lines from 'i' where there's a blank line.  If we cannot find
      # a blank line, then we will show up to 10 lines from i.
      try:
        j = stripped_lines[i:-1].index('')
      except ValueError:
        j = 10
      # Print from either 15 lines back from i or the start of the log
      # text to j lines after i.
      return ''.join(lines[max(i-15, 0):i+j])
    except ValueError:
      pass
  return False


def json_probe(sensitive, allports):
  """Looks through the port range and finds a main listening.
  sensitive: Indicates whether partial success should be reported.

  Returns (port, name) or None.
  """
  procs = {}
  for ports in sublists(allports, 30):
    for port in ports:
      # urllib2 does not play nicely with threading. Using curl lets us avoid
      # the GIL.
      procs[port] = subprocess2.Popen(
          ['curl', '-fs', '-m2', 'http://localhost:%d/json/project' % port],
          stdin=subprocess2.VOID,
          stdout=subprocess2.PIPE,
          stderr=subprocess2.VOID)
    for port in ports:
      stdout, _ = procs[port].communicate()
      if procs[port].returncode != 0:
        continue
      try:
        data = json.loads(stdout) or {}
        if not data or (not 'projectName' in data and not 'title' in data):
          logging.debug('Didn\'t get valid data from port %d' % port)
          if sensitive:
            return (port, None)
          continue
        name = data.get('projectName', data.get('title'))
        return (port, name)
      except ValueError:
        logging.warning('Didn\'t get valid data from port %d' % port)
        # presume this is some other type of server
        #  E.g. X20 on a dev workstation.
        continue

  return None


def wait_for_start(main, name, path, ports):
  """Waits for ~30s for the mains to open its web server."""
  logging.info("Waiting for main %s on ports %s" % (name, ports))
  for i in range(300):
    result = json_probe(False, ports)
    if result is None:
      exception = search_for_exceptions(path)
      if exception:
        return exception
      time.sleep(0.1)
      continue
    port, got_name = result # pylint: disable=unpacking-non-sequence
    if got_name != name:
      return 'Wrong %s name, expected %s, got %s on port %d' % (
          main, name, got_name, port)
    logging.info("Found main %s on port %s, iteration %d" % (name, port, i))
    # The server is now answering /json requests. Check that the log file
    # doesn't have any other exceptions just in case there was some other
    # unexpected error.
    return search_for_exceptions(path)

  return 'Didn\'t find open port for %s' % main


def check_for_no_mains():
  ports = range(8000, 8099) + range(8200, 8299) + range(9000, 9099)
  ports = [x for x in ports if x not in mainmap.PORT_BLACKLIST]
  result = json_probe(True, ports)
  if result is None:
    return True
  if result[1] is None:
    logging.error('Something is listening on port %d' % result[0])
    return False
  logging.error('Found unexpected main %s on port %d' %
                (result[1], result[0]))
  return False
