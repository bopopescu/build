#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Removes checkouts from try subordinates."""

import os
import subprocess
import sys

ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')


def parse_main(main):
  sys.path.append(os.path.join(ROOT_DIR, 'scripts', 'main', 'unittests'))
  import test_env  # pylint: disable=F0401,W0612

  mainpath = os.path.join(ROOT_DIR, 'mains', main)
  os.chdir(mainpath)
  variables = {}
  main = os.path.join(mainpath, 'main.cfg')
  execfile(main, variables)
  return variables['c']


def main():
  """It starts a fake in-process buildbot main just enough to parse
  main.cfg.

  Then it queries all the builders and all the subordinates to determine the current
  configuration and process accordingly.
  """
  c = parse_main('main.tryserver.chromium.linux')
  print 'Parsing done.'

  # Create a mapping of subordinatebuilddir with each subordinates connected to it.
  subordinatebuilddirs = {}
  # Subordinates per OS
  all_subordinates = {}
  for builder in c['builders']:
    builder_os = builder['name'].split('_', 1)[0]
    if builder_os in ('cros', 'android'):
      builder_os = 'linux'
    subordinatenames = set(builder['subordinatenames'])

    all_subordinates.setdefault(builder_os, set())
    all_subordinates[builder_os] |= subordinatenames

    subordinatebuilddir = builder.get('subordinatebuilddir', builder['name'])
    subordinatebuilddirs.setdefault(builder_os, {})
    subordinatebuilddirs[builder_os].setdefault(subordinatebuilddir, set())
    subordinatebuilddirs[builder_os][subordinatebuilddir] |= subordinatenames

  # Queue of commands to run, per subordinate.
  queue = {}
  for builder_os, subordinatebuilddirs in subordinatebuilddirs.iteritems():
    os_subordinates = all_subordinates[builder_os]
    for subordinatebuilddir, subordinates in subordinatebuilddirs.iteritems():
      for subordinate in os_subordinates - subordinates:
        queue.setdefault((builder_os, subordinate), []).append(subordinatebuilddir)

  print 'Out of %d subordinates, %d will be cleaned' % (len(c['subordinates']), len(queue))
  commands = []
  for key in sorted(queue):
    subordinate_os, subordinatename = key
    dirs = queue[key]
    if subordinate_os == 'win':
      cmd = 'cmd.exe /c rd /q %s' % ' '.join(
          'e:\\b\\build\\subordinate\\%s' % s for s in dirs)
    else:
      cmd = 'rm -rf %s' % ' '.join('/b/build/subordinate/%s' % s for s in dirs)
    commands.append(('ssh', subordinatename, cmd))

  # TODO(maruel): Use pssh.
  failed = []
  for command in commands:
    print ' '.join(command[1:])
    if subprocess.call(command):
      failed.append(command[1])

  if failed:
    print 'These subordinates failed:'
    for i in failed:
      print ' %s' % i
  return 0


if __name__ == '__main__':
  sys.exit(main())
