#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prints information from main_site_config.py

The sole purpose of this program it to keep the crap inside build/ while
we're moving to the new infra/ repository. By calling it, you get access
to some information contained in main_site_config.py for a given main,
as a json string.

Invocation: runit.py get_main_config.py --main-name <main name>
"""

import argparse
import inspect
import json
import logging
import os
import sys

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
# Directory containing build/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
assert os.path.isdir(os.path.join(ROOT_DIR, 'build')), \
       'Script may have moved in the hierarchy'

LOGGER = logging


def get_main_directory(main_name):
  """Given a main name, returns the full path to the corresponding directory.

  This function either returns a path to an existing directory, or None.
  """
  if main_name.startswith('main.'):
    main_name = main_name[7:]

  # Look for the main directory
  for build_name in ('build', 'build_internal'):
    main_path = os.path.join(ROOT_DIR,
                               build_name,
                               'mains',
                               'main.' + main_name)

    if os.path.isdir(main_path):
      return main_path
  return None


def read_main_site_config(main_name):
  """Return a dictionary containing main_site_config

  main_name: name of main whose file to parse

  Return: dict (empty dict if there is an error)
  {'main_port': int()}
  """
  main_path = get_main_directory(main_name)

  if not main_path:
    LOGGER.error('full path for main cannot be determined')
    return {}

  main_site_config_path = os.path.join(main_path, 'main_site_config.py')

  if not os.path.isfile(main_site_config_path):
    LOGGER.error('no main_site_config.py file found in %s' % main_path)
    return {}

  local_vars = {}
  try:
    execfile(main_site_config_path, local_vars)
  except Exception:  # pylint: disable=W0703
    # Naked exceptions are banned by the style guide but we are
    # trying to be resilient here.
    LOGGER.exception("exception occured when exec'ing %s"
                     % main_site_config_path)
    return {}

  for _, symbol in local_vars.iteritems():
    if inspect.isclass(symbol):
      if not hasattr(symbol, 'main_port'):
        continue

      config = {'main_port': symbol.main_port}
      for attr in ('project_name', 'subordinate_port', 'main_host',
                   'main_port_alt', 'buildbot_url'):
        if hasattr(symbol, attr):
          config[attr] = getattr(symbol, attr)
      return config

  LOGGER.error('No main port found in %s' % main_site_config_path)
  return {}


def get_options(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('--main-name', required=True)

  return parser.parse_args(argv)


def main():
  options = get_options(sys.argv[1:])
  config = read_main_site_config(options.main_name)
  print json.dumps(config, indent=2, sort_keys=True)
  return 0


if __name__ == '__main__':
  sys.exit(main())
