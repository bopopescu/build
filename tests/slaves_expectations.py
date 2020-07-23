#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Dumps a list of known subordinates, along with their OS and main."""

import argparse
import collections
import json
import logging
import os
import subprocess
import sys

# This file is located inside tests. Update this path if that changes.
BUILD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BUILD, 'scripts')
LIST_SLAVES = os.path.join(SCRIPTS, 'tools', 'list_subordinates.py')

sys.path.append(SCRIPTS)

from common import chromium_utils


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-g',
    '--gen',
    '--generate',
    action='store_true',
    dest='generate',
    help='Generate subordinates.expected for all mains.',
  )
  args = parser.parse_args()

  mains = chromium_utils.ListMainsWithSubordinates()
  main_map = {}

  for main_path in mains:
    # Convert ~/<somewhere>/main.<whatever> to just whatever.
    main = os.path.basename(main_path).split('.', 1)[-1]
    botmap = json.loads(subprocess.check_output([
        LIST_SLAVES, '--json', '--main', main]))

    subordinate_map = collections.defaultdict(set)

    for entry in botmap:
      assert entry['mainname'] == 'main.%s' % main

      for builder in entry['builder']:
        subordinate_map[builder].add(entry['hostname'])

    main_map[main_path] = {}

    for buildername in sorted(subordinate_map.keys()):
      main_map[main_path][buildername] = sorted(subordinate_map[buildername])

  retcode = 0

  for main_path, subordinates_expectation in main_map.iteritems():
    if os.path.exists(main_path):
      subordinates_expectation_file = os.path.join(main_path, 'subordinates.expected')

      if args.generate:
        with open(subordinates_expectation_file, 'w') as fp:
          json.dump(subordinates_expectation, fp, indent=2, sort_keys=True)
        print 'Wrote expectation: %s.' % subordinates_expectation_file
      else:
        if os.path.exists(subordinates_expectation_file):
          with open(subordinates_expectation_file) as fp:
            if json.load(fp) != subordinates_expectation:
              logging.error(
                  'Mismatched expectation: %s.', subordinates_expectation_file)
              retcode = 1
        else:
          logging.error('File not found: %s.', subordinates_expectation_file)
          retcode = 1

  return retcode


if __name__ == '__main__':
  sys.exit(main())
