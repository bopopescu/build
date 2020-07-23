#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs a command with PYTHONPATH set up for the Chromium build setup.

This is helpful for running scripts locally on a development machine.

Try `scripts/common/runit.py python`
or  (in scripts/subordinate): `../common/runit.py runtest.py --help`
"""

import optparse
import os
import subprocess
import sys

# Directory where this script (runit.py) lives (i.e. scripts/tools)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# Import 'common.env' from 'scripts' directory to load our Infra PYTHONPATH
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
import common.env

USAGE = '%s [options] <command to run>' % os.path.basename(sys.argv[0])


def main():
  option_parser = optparse.OptionParser(usage=USAGE)
  option_parser.add_option('-s', '--show-path', action='store_true',
                           help='display new PYTHONPATH before running command')
  option_parser.disable_interspersed_args()
  options, args = option_parser.parse_args()
  if not args:
    option_parser.error('Must provide a command to run.')

  # If the first argument is 'python', replace it with the system executable.
  if args[0] == 'python':
    args[0] = sys.executable

  with common.env.GetInfraPythonPath().Enter():
    if options.show_path:
      print 'Set PYTHONPATH: %s' % os.environ['PYTHONPATH']
    # Use subprocess instead of execv because otherwise windows destroys
    # quoting.
    return subprocess.call(args)


if __name__ == '__main__':
  sys.exit(main())
