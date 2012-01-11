#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A tool to extract a build, executed by a buildbot slave.
"""

import optparse
import os
import shutil
import sys
import traceback
import urllib
import urllib2

from common import chromium_utils
from slave import slave_utils


# Exit code to use for warnings, to distinguish script issues.
WARNING_EXIT_CODE = 88


@chromium_utils.RunAndPrintDots
def urlretrieve(*args, **kwargs):
  return urllib.urlretrieve(*args, **kwargs)


def real_main(options, args):
  """ Download a build, extract it to build\BuildDir\full-build-win32
      and rename it to build\BuildDir\Target
  """
  # TODO: need to get the build *output* directory passed in also so Linux
  # and Mac don't have to walk up a directory to get to the right directory.
  build_output_dir = None
  if chromium_utils.IsWindows():
    build_output_dir = options.build_dir
  elif chromium_utils.IsLinux():
    build_output_dir = os.path.join(os.path.dirname(options.build_dir),
                                   'sconsbuild')
  elif chromium_utils.IsMac():
    build_output_dir = os.path.join(os.path.dirname(options.build_dir),
                                   'xcodebuild')
  else:
    raise NotImplementedError('%s is not supported.' % sys.platform)

  abs_build_dir = os.path.abspath(options.build_dir)
  abs_build_output_dir = os.path.abspath(build_output_dir)
  target_build_output_dir = os.path.join(abs_build_output_dir, options.target)

  # Find the revision that we need to download.
  current_revision = slave_utils.SubversionRevision(abs_build_dir)

  webkit_revision = None
  if options.webkit_dir:
    webkit_revision = slave_utils.SubversionRevision(
        os.path.join(abs_build_dir, '..', options.webkit_dir))

  # Generic name for the archive.
  archive_name = 'full-build-%s.zip' % chromium_utils.PlatformName()

  # Just take the zip off the name for the output directory name.
  output_dir = os.path.join(abs_build_output_dir,
                            archive_name.replace('.zip', ''))

  # Insert parentslavename if it's present.
  try:
    options.build_url = options.build_url % {
        'parentslavename': options.build_properties.get('parentslavename', '')
    }
  except KeyError:
    # This condition is hit when a build_url is passed that does not contain
    # the key 'parentslavename'.  We silently ignore this error.
    pass
  print 'Build URL: %s' % options.build_url

  # URL containing the version number.
  if not webkit_revision:
    url = options.build_url.replace('.zip', '_%d.zip' % current_revision)
  else:
    url = options.build_url.replace(
        '.zip', '_wk%d_%d.zip' % (webkit_revision, current_revision))

  # We try to download and extract 3 times.
  for tries in range(1, 4):
    print 'Try %d: Fetching build from %s...' % (tries, url)

    failure = False

    # Check if the url exists.
    try:
      content = urllib2.urlopen(url)
      content.close()
    except urllib2.HTTPError:
      print '%s is not found' % url
      failure = True

      # When 'halt_on_missing_build' is present in factory_properties and if
      # 'revision' is set in build properties, we assume the build is
      # triggered automatically and so we halt on a missing build zip.  The
      # other case is if the build is forced, in which case we keep trying
      # later by looking for the latest build that's available.
      if (options.factory_properties.get('halt_on_missing_build', False) and
          'revision' in options.build_properties and
          options.build_properties['revision'] != ''):
        return -1

    # If the url is valid, we download the file.
    if not failure:
      try:
        urlretrieve(url, archive_name)
        print '\nDownload complete'
      except IOError:
        print '\nFailed to download archived build'
        failure = True

    # If the versioned url failed, we try to get the latest build.
    if failure:
      print 'Fetching latest build...'
      try:
        urlretrieve(options.build_url, archive_name)
        print '\nDownload complete'
      except IOError:
        print '\nFailed to download generic archived build'
        # Try again...
        continue

    print 'Extracting build %s to %s...' % (archive_name, abs_build_output_dir)
    try:
      chromium_utils.RemoveDirectory(target_build_output_dir)
      chromium_utils.ExtractZip(archive_name, abs_build_output_dir)
      # For Chrome builds, the build will be stored in chrome-win32.
      chrome_win32_dir = output_dir.replace('full-build-win32', 'chrome-win32')
      if os.path.exists(chrome_win32_dir):
        shutil.move(chrome_win32_dir, target_build_output_dir)
      else:
        shutil.move(output_dir, target_build_output_dir)
    except (OSError, IOError):
      print 'Failed to extract the build.'
      # Print out the traceback in a nice format
      traceback.print_exc()
      # Try again...
      continue

    # If we got the latest build, then figure out its revision number.
    if failure:
      print "Trying to determine the latest build's revision number..."
      try:
        build_revision_file_name = os.path.join(
            target_build_output_dir,
            chromium_utils.FULL_BUILD_REVISION_FILENAME)
        build_revision_file = open(build_revision_file_name, 'r')
        print 'Latest build is revision: %s' % build_revision_file.read()
        build_revision_file.close()
      except IOError:
        print "Could not determine the latest build's revision number"

    if failure:
      # We successfully extracted the archive, but it was the generic one.
      return WARNING_EXIT_CODE
    return 0

  # If we get here, that means that it failed 3 times. We return a failure.
  return -1


def main():
  option_parser = optparse.OptionParser()

  option_parser.add_option('', '--target',
                           help='build target to archive (Debug or Release)')
  option_parser.add_option('', '--build-dir',
                           help='path to main build directory (the parent of '
                                'the Release or Debug directory)')
  option_parser.add_option('', '--build-url',
                           help='url where to find the build to extract')
  # TODO(cmp): Remove --halt-on-missing-build when the buildbots are upgraded
  #            to not use this argument.
  option_parser.add_option('--halt-on-missing-build', action='store_true',
                           default=False,
                           help='whether to halt on a missing build')
  option_parser.add_option('--build-properties', action='callback',
                           callback=chromium_utils.convert_json, type='string',
                           nargs=1, default={},
                           help='build properties in JSON format')
  option_parser.add_option('--factory-properties', action='callback',
                           callback=chromium_utils.convert_json, type='string',
                           nargs=1, default={},
                           help='factory properties in JSON format')
  option_parser.add_option('', '--webkit-dir', default=None,
                           help='webkit directory path, '
                                'relative to --build-dir')

  options, args = option_parser.parse_args()
  return real_main(options, args)


if '__main__' == __name__:
  sys.exit(main())
