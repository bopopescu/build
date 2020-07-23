#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script automates fixing broken Windows bots after svn2git coversion.

The script is designed to be run manually, not automatically.

It follows the same steps as described in https://crbug.com/498256#c105. Each
command execution needs to be confirmed by the user, which should inspect
results of the previous command and only continue if there were no unexpected
errors. Most typical error is when a file is locked by some process and the
easiest solution is typically to reboot the bot and try running the script
again.
"""


import os
import subprocess
import sys


SLAVE_GCLIENT_CONFIG = """solutions = [
  {
    "name"      : "subordinate.DEPS",
    "url"       : "https://chrome-internal.googlesource.com/chrome/tools/build/slave.DEPS.git",
    "deps_file" : ".DEPS.git",
    "managed"   : True,
  },
]"""

INTERNAL_GCLIENT_CONFIG = """solutions = [
  {
    "name"      : "internal.DEPS",
    "url"       : "https://chrome-internal.googlesource.com/chrome/tools/build/internal.DEPS.git",
    "deps_file" : ".DEPS.git",
    "managed"   : True,
  },
]"""


def query_yes_no(question, default="yes"):
  """Ask a yes/no question via raw_input() and return their answer.

  "question" is a string that is presented to the user.
  "default" is the presumed answer if the user just hits <Enter>.
      It must be "yes" (the default), "no" or None (meaning
      an answer is required of the user).

  The "answer" return value is True for "yes" or False for "no".
  """
  valid = {"yes": True, "y": True, "ye": True,
           "no": False, "n": False}
  if default is None:
    prompt = " [y/n] "
  elif default == "yes":
    prompt = " [Y/n] "
  elif default == "no":
    prompt = " [y/N] "
  else:
    raise ValueError("invalid default answer: '%s'" % default)

  while True:
    sys.stdout.write(question + prompt)
    choice = raw_input().lower()
    if default is not None and choice == '':
      return valid[default]
    elif choice in valid:
      return valid[choice]
    else:
      sys.stdout.write("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")


def main():
  assert sys.platform.startswith('cygwin')

  cmd_env = os.environ.copy()
  cmd_path = [p for p in os.environ['PATH'].split(':') if 'cygdrive' in p]

  if os.path.exists('/cygdrive/c/b'):
    b_dir = '/cygdrive/c/b'
    cmd_env['AWS_CREDENTIAL_FILE'] = 'C:\\b\\site_config\\.boto'
    cmd_path.extend(['/cygdrive/c/b/depot_tools', '/cygdrive/c/b/depot_tools2'])
  else:
    b_dir = '/cygdrive/e/b'
    cmd_env['AWS_CREDENTIAL_FILE'] = 'E:\\b\\site_config\\.boto'
    cmd_path.extend(['/cygdrive/e/b/depot_tools', '/cygdrive/e/b/depot_tools2'])

  cmd_env['PATH'] = ':'.join(cmd_path)

  assert os.path.exists(b_dir), 'Failed to find b-directory'
  assert os.curdir == b_dir or not os.curdir.startswith(b_dir), ('This script '
      'must not be run from any of the subdirs of %s because bash will lock '
      'these subdirs and we will not be able to move/delete them' % b_dir)

  if os.path.exists(os.path.join(b_dir, 'subordinate.DEPS')):
    gclient_config = SLAVE_GCLIENT_CONFIG
  else:
    gclient_config = INTERNAL_GCLIENT_CONFIG

  def call_bash(*cmd):
    if query_yes_no('Run %s in bash?' % (cmd,)):
      subprocess.call(list(cmd), shell=True)

  def call_cmd(*cmd):
    if query_yes_no('Run %s in cmd?' % (cmd,)):
      subprocess.call(['cmd.exe', '/C'] + list(cmd), env=cmd_env)

  def chdir(new_dir):
    print 'Changing dir to %s' % new_dir
    os.chdir(new_dir)

  call_cmd('taskkill', '/F', '/T', '/IM', 'python.exe')
  chdir(b_dir)

  print ('Note that following set of commands frequently fails due to files '
         'being locked by Windows. If this happens, please try rebooting the '
         'machine and running this script again as soon as possible after the '
         'restart (before a build starts and files get locked again).')
  call_bash('mv build/site_config site_config; '
            'mv depot_tools depot_tools2; '
            'mkdir _del; '
            'mv build* .gclient* *.DEPS subordinate_svn_to_git* _del')

  print 'Creating new .gclient'
  with open('.gclient', 'w') as fo:
    fo.write(gclient_config)

  call_cmd('gclient', 'sync')
  call_bash('mv depot_tools/.git depot_tools2/.git')
  call_bash('rm -rf depot_tools')
  call_bash('mv depot_tools2 depot_tools')
  chdir('depot_tools')
  call_bash('git reset --hard')
  call_bash('git reset --hard')
  chdir('..')
  call_bash('mv site_config/.bot* build/site_config')
  call_bash('mv site_config _del')
  call_cmd('gclient sync')
  call_bash('rm -rf _del; shutdown -r 0')


if __name__ == '__main__':
  main()
