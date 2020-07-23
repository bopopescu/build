#!/usr/bin/python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function

import argparse
import os
import re
import sys


TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.dirname(TOOLS_DIR)
BASE_DIR = os.path.dirname(SCRIPTS_DIR)

# This adjusts sys.path, so must be done before we import other modules.
if not SCRIPTS_DIR in sys.path:  # pragma: no cover
  sys.path.append(SCRIPTS_DIR)

from common import chromium_utils
from common import filesystem


TEMPLATE_SUBPATH = os.path.join('scripts', 'tools', 'buildbot_tool_templates')
TEMPLATE_DIR = os.path.join(BASE_DIR, TEMPLATE_SUBPATH)


def main(argv, fs):
  args = parse_args(argv)
  return args.func(args, fs)


def parse_args(argv):
  parser = argparse.ArgumentParser()
  subps = parser.add_subparsers()

  subp = subps.add_parser('gen', help=run_gen.__doc__)
  subp.add_argument('main_dirname', nargs=1,
                    help='Path to main config directory (must contain '
                         'a builders.pyl file).')
  subp.set_defaults(func=run_gen)

  subp = subps.add_parser('genall', help=run_gen_all.__doc__)
  subp.set_defaults(func=run_gen_all)

  subp = subps.add_parser('help', help=run_help.__doc__)
  subp.add_argument(nargs='?', action='store', dest='subcommand',
                    help='The command to get help for.')
  subp.set_defaults(func=run_help)

  return parser.parse_args(argv)


def generate(builders_path, fs, print_prefix=''):
  """Generate a new main config."""

  out_dir = fs.dirname(builders_path)
  out_subpath = fs.relpath(out_dir, BASE_DIR)
  values = chromium_utils.ParseBuildersFileContents(
      builders_path,
      fs.read_text_file(builders_path))

  for filename in fs.listfiles(TEMPLATE_DIR):
    template = fs.read_text_file(fs.join(TEMPLATE_DIR, filename))
    contents = _expand(template, values,
                       '%s/%s' % (TEMPLATE_SUBPATH, filename),
                       out_subpath)
    fs.write_text_file(fs.join(out_dir, filename), contents)
    print('%sWrote %s.' % (print_prefix, filename))

  return 0


def run_gen(args, fs):
  """Generate a new main config."""

  main_dirname = args.main_dirname[0]
  builders_path = fs.join(main_dirname, 'builders.pyl')

  if not fs.exists(builders_path):
    print("%s not found" % builders_path, file=sys.stderr)
    return 1

  generate(builders_path, fs)
  return 0


def run_gen_all(args, fs):
  """Generate new main configs for all mains that use builders.pyl."""

  mains_dirs = [
    fs.join(BASE_DIR, 'mains'),
    fs.join(BASE_DIR, '..', 'build_internal', 'mains'),
  ]
  for mains_dir in mains_dirs:
    if not fs.isdir(mains_dir):
      continue
    for main_dir in fs.listdirs(mains_dir):
      if not main_dir.startswith('main.'):
        continue
      builders_path = fs.join(mains_dir, main_dir, 'builders.pyl')
      if fs.isfile(builders_path):
        print('%s:' % main_dir)
        generate(builders_path, fs, print_prefix='  ')
  return 0


def run_help(args, fs):
  """Get help on a subcommand."""

  if args.subcommand:
    return main([args.subcommand, '--help'], fs)
  return main(['--help'], fs)


def _expand(template, values, source, main_subpath):
  try:
    contents = template % values
  except:
    print("Error populating template %s" % source, file=sys.stderr)
    raise
  return _update_generated_file_disclaimer(contents, source, main_subpath)


def _update_generated_file_disclaimer(contents, source, main_subpath):
  pattern = '# This file is used by scripts/tools/buildbot-tool.*'
  replacement = ('# This file was generated from\n'
                 '# %s\n'
                 '# by "../../build/scripts/tools/buildbot-tool gen .".\n'
                 '# DO NOT EDIT BY HAND!\n' % source)
  return re.sub(pattern, replacement, contents)


if __name__ == '__main__':  # pragma: no cover
  sys.exit(main(sys.argv[1:], filesystem.Filesystem()))
