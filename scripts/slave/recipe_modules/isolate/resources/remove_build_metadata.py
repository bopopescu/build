#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Remove the build metadata embedded in the artifacts of a build."""

import json
import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_files_to_clean(build_dir, recursive=False):
  """Get the list of files to clean."""
  allowed = frozenset(
      ('', '.apk', '.app', '.dll', '.dylib', '.exe', '.nexe', '.so'))
  non_x_ok_exts = frozenset(('.apk', '.isolated'))
  min_timestamp = 0
  if os.path.exists(os.path.join(build_dir, 'build.ninja')):
    min_timestamp = os.path.getmtime(os.path.join(build_dir, 'build.ninja'))

  def check(f):
    if not os.path.isfile(f) or os.path.basename(f).startswith('.'):
      return False
    if os.path.getmtime(os.path.join(build_dir, f)) < min_timestamp:
      return False
    ext = os.path.splitext(f)[1]
    return (ext in non_x_ok_exts) or (ext in allowed and os.access(f, os.X_OK))

  ret_files = set()
  for root, dirs, files in os.walk(build_dir):
    if not recursive:
      dirs[:] = [d for d in dirs if d.endswith('_apk')]
    for f in (f for f in files if check(os.path.join(root, f))):
      ret_files.add(os.path.relpath(os.path.join(root, f), build_dir))
  return ret_files


def run_zap_timestamp(src_dir, filepath):
  """Run zap_timestamp.exe on a PE binary."""
  assert sys.platform == 'win32'
  syzygy_dir = os.path.join(
      src_dir, 'third_party', 'syzygy', 'binaries', 'exe')
  zap_timestamp_exe = os.path.join(syzygy_dir, 'zap_timestamp.exe')
  print('Processing: %s' % os.path.basename(filepath))
  proc = subprocess.Popen(
      [zap_timestamp_exe, '--input-image=%s' % filepath, '--overwrite'],
      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  log, _ = proc.communicate()
  if proc.returncode != 0:
    print >> sys.stderr, log
  return proc.returncode


def remove_pe_metadata(filename, src_dir):
  """Remove the build metadata from a PE file."""
  # Only run zap_timestamp on the PE files for which we have a PDB.
  ret = 0
  if os.path.exists(filename + '.pdb'):
    ret = run_zap_timestamp(src_dir, filename)
  return ret


def remove_apk_timestamps(filename):
  """Remove the timestamps embedded in an apk archive."""
  print('Processing: %s' % os.path.basename(filename))
  with zipfile.ZipFile(filename, 'r') as zf:
    # Creates a temporary file.
    out_file, out_filename = tempfile.mkstemp(prefix='remote_apk_timestamp')
    os.close(out_file)
    try:
      with zipfile.ZipFile(out_filename, 'w') as zf_o:
        # Copy the data from the original file to the new one.
        for info in zf.infolist():
          # Overwrite the timestamp with a constant value.
          info.date_time = (1980, 1, 1, 0, 0, 0)
          zf_o.writestr(info, zf.read(info.filename))
      # Remove the original file and replace it by the modified one.
      os.remove(filename)
      shutil.move(out_filename, filename)
    finally:
      if os.path.isfile(out_filename):
        os.remove(out_filename)


def remove_metadata(build_dir, src_dir, recursive):
  """Remove the build metadata from the artifacts of a build."""
  with open(os.path.join(BASE_DIR, 'deterministic_build_blacklist.json')) as f:
    blacklist = frozenset(json.load(f))
  files = get_files_to_clean(build_dir, recursive) - blacklist
  failed_files = []
  ret = 0
  for f in files:
    if f.endswith(('.dll', '.exe')):
      if remove_pe_metadata(os.path.join(build_dir, f), src_dir):
        ret = 1
        failed_files.append(f)
    elif f.endswith('.apk'):
      remove_apk_timestamps(os.path.join(build_dir, f))

  if failed_files:
    print >> sys.stderr, 'Failed for the following files:'
    print >> sys.stderr, '\n'.join('  ' + i for i in sorted(failed_files))
    return 1

  return ret


def main():
  parser = optparse.OptionParser(usage='%prog [options]')
  # TODO(sebmarchand): Add support for reading the list of artifact from a
  # .isolated file.
  parser.add_option('--build-dir', help='The build directory.')
  parser.add_option('--src-dir', help='The source directory.')
  parser.add_option('-r', '--recursive', action='store_true', default=False,
                    help='Indicates if the script should be recursive.')
  options, _ = parser.parse_args()

  if not options.build_dir:
    parser.error('--build-dir is required')

  if sys.platform == 'win32' and not options.src_dir:
    parser.error('--src-dir is required')

  return remove_metadata(options.build_dir, options.src_dir, options.recursive)


if __name__ == '__main__':
  sys.exit(main())
