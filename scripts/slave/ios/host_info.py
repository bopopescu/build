#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Print information about the tools present on this machine.

Usage:
  ./host_info.py -j /tmp/out.json

  Writes a json dictionary containing tools information.
"""

import argparse
import json
import multiprocessing
import os
import platform
import sys

from subordinate.ios import utils


def check_for_tools():
  """Checks for the presence of some required tools.

  Returns:
    A list of tools present, a list of tools missing.
  """
  available = []
  missing = []

  # A list of tools that should be present in PATH.
  tools = [
    utils.PLIST_BUDDY,
  ]

  def try_call(binary):
    try:
      utils.call(binary)
      available.append(binary)
    except OSError:
      missing.append(binary)

  for tool in tools:
    try_call(tool)

  return available, missing


def extract_xcode_version(out):
  """Extracts Xcode version information from the given xcodebuild output.

  Args:
    out: List of lines emitted by an xcodebuild -version call.

  Returns:
    A 2-tuple of (Xcode Version, Xcode Build Version).
  """
  # Sample output:
  # Xcode 5.0
  # Build version 5A1413
  ver = None
  build_ver = None

  if len(out) > 0:
    if ' ' in out[0]:
      ver = out[0].split()[-1]
    if len(out) > 1:
      if ' ' in out[1]:
        build_ver = out[1].split()[-1]

  return ver, build_ver


def extract_sdks(out):
  """Extracts Xcode SDK information from the given xcodebuild output.

  Args:
    out: List of lines emitted by an xcodebuild -showsdks call.

  Returns:
    A list of valid parameters to xcodebuild -sdk.
  """
  # Sample output:
  # OS X SDKs:
  #     Mac OS X 10.6                   -sdk macosx10.6
  #     OS X 10.8                       -sdk macosx10.8
  #
  # iOS SDKs:
  #     iOS 7.0                         -sdk iphoneos7.0
  #
  # iOS Simulator SDKs:
  #     Simulator - iOS 6.1             -sdk iphonesimulator6.1
  #     Simulator - iOS 7.0             -sdk iphonesimulator7.0
  return [line.split('-sdk')[-1].strip() for line in out if '-sdk' in line]


def get_free_disk_space():
  """Returns the amount of free space on the current disk, in GiB.

  Returns:
    The amount of free space on the current disk, measured in GiB.
  """
  # Stat the current path for info on the current disk.
  stat = os.statvfs('.')
  # Multiply block size by number of free blocks, express in GiB.
  return stat.f_frsize * stat.f_bavail / 1024.0 / 1024.0 / 1024.0


def get_num_cpus():
  """Returns the number of logical CPUs on this machine.

  Returns:
    The number of logical CPUs on this machine, or 'unknown' if indeterminate.
  """
  try:
    return multiprocessing.cpu_count()
  except NotImplementedError:
    return 'unknown'


def get_python_version():
  """Returns the version of Python running this script.

  Returns:
    A Python version string.
  """
  return platform.python_version()


def get_python_location():
  """Returns the location of the Python interpreter running this script.

  Returns:
    The full path to the current Python interpreter.
  """
  return sys.executable


def get_osx_version():
  """Returns the version of Mac OS X installed on this host.

  Returns:
    The Mac version string, or the empty string if this host is not a Mac.
  """
  return platform.mac_ver()[0]


def main(json_file):
  """Extracts information about the tools present on this host.

  Args:
    json_file: File to write JSON containing the tools information.
  """
  info = {
  }

  info['Xcode Version'], info['Xcode Build Version'] = extract_xcode_version(
    utils.call('xcodebuild', '-version').stdout)

  info['Xcode SDKs'] = extract_sdks(
    utils.call('xcodebuild', '-showsdks').stdout)

  info['Free Space'] = get_free_disk_space()
  info['Logical CPUs'] = get_num_cpus()
  info['Python Version'] = get_python_version()
  info['Python Location'] = get_python_location()
  info['Mac OS X Version'] = get_osx_version()

  info['Available Tools'], info['Missing Tools'] = check_for_tools()

  if json_file:
    with open(json_file, 'w') as json_file:
      json.dump(info, json_file)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-j',
    '--json-file',
    help='Location to write a JSON summary.',
    metavar='file',
    type=str,
  )

  sys.exit(main(parser.parse_args().json_file))
