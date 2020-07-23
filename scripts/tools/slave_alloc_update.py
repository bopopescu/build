#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Command-line tool to update subordinate allocation JSON for subordinate pools that are
managed by `<build>/scripts/common/subordinate_alloc.py`.

This script is directed at a main, and will:
  1) Load the main's `subordinates.cfg` and process it.
  2) For each identified SubordinateAllocator instance, regenerate the subordinate pool JSON
     file.
"""

import argparse
import logging
import os
import sys

import common.chromium_utils
import common.env
import common.subordinate_alloc


def _UpdateSubordinateAlloc(main_dir, sa):
  logging.info('Updating subordinates for main "%s": [%s]',
               os.path.basename(main_dir), sa.state_path)
  with common.chromium_utils.MainEnvironment(main_dir):
    sa.SaveState()


def _UpdateMain(main_name):
  main_dir = common.chromium_utils.MainPath(main_name)
  subordinates_cfg_path = os.path.join(os.path.abspath(main_dir), 'subordinates.cfg')
  if not os.path.isfile(subordinates_cfg_path):
    raise ValueError('Main directory does not contain "subordinates.cfg": %s' % (
                     main_dir,))

  logging.debug('Loading "subordinates.cfg" from: [%s]', subordinates_cfg_path)
  cfg = common.chromium_utils.ParsePythonCfg(subordinates_cfg_path, fail_hard=False)

  updated = False
  for name, sa in (cfg or {}).iteritems():
    if isinstance(sa, common.subordinate_alloc.SubordinateAllocator):
      logging.debug('Identified subordinate allocator variable [%s]', name)
      _UpdateSubordinateAlloc(main_dir, sa)
      updated = True
  return updated


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose',
      action='count', default=0,
      help='Increase verbosity. This can be specified multiple times.')
  parser.add_argument('mains', metavar='NAME', nargs='+',
      help='Name of the main to update.')
  args = parser.parse_args(argv)

  # Configure logging verbosity.
  if args.verbose == 0:
    level = logging.WARNING
  elif args.verbose == 1:
    level = logging.INFO
  else:
    level = logging.DEBUG
  logging.getLogger().setLevel(level)

  # Update each main directory.
  for name in args.mains:
    if not _UpdateMain(name):
      raise ValueError('No subordinate allocators identified for [%s]' % (name,))


if __name__ == '__main__':
  logging.basicConfig()
  try:
    sys.exit(main(sys.argv[1:]))
  except Exception as e:
    logging.exception('Uncaught exception encountered during execution: %s', e)
    sys.exit(2)
