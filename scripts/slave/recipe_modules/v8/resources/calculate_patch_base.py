#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to calculate the latest fitting git commit hash for a patch.

A commit fits if the hashes of all base files from the patch are equal to
the hashes of the respective files from the commit. As multiple such commits
might exist, this returns the latest.

This looks back for a maximum of 1000 commits. Doesn't support windows.

Expects three arguments:
1) a file containing the raw patch,
2) folder with the checkout,
3) a file to write the result hash to.
"""

import os
import subprocess
import sys

# The revision from which v8 coverage is supported.
# TODO(machenbach): Remove this as soon as it's supported for 1000+ revisions. 
V8_COVERAGE_SUPPORT_COMMIT = 'e7f99c1ed52a5724ffef41c361920786e97f240d'

assert len(sys.argv) == 4

# Read the raw patch.
with open(sys.argv[1]) as f:
  patch = f.read()

# Absolute path to checkout folder.
CHECKOUT = sys.argv[2]
assert os.path.exists(CHECKOUT) and os.path.isdir(CHECKOUT)

# Parse the patch and extract (file, hsh) tuples. The hsh is the hash of the
# base file of a given file.
base_hashes = []
current_file = None
for line in patch.splitlines():
  if line.startswith('Index: '):
    # "Index" header looks like this:
    # Index: <file name>
    current_file = line.split('Index: ')[1]
  elif line.startswith('copy from '):
    # If diff considers a file to be a copy of an existing file, the base hash
    # is from the existing file. In this case, the diff contains a line after
    # "Index" and before "index" that looks like:
    # copy from <old file name>
    current_file = line.split('copy from ')[1]
  elif line.startswith('rename from '):
    # Same as above with rename.
    current_file = line.split('rename from ')[1]
  elif line.startswith('index '):
    # "index" header looks like this and comes a few lines after the one above:
    # index <base hash>..<hash after patch> <mode>
    assert current_file
    hsh = line.split(' ')[1].split('..')[0]
    if len(hsh) * '0' != hsh:
      # We only care for existing files. New ones have a sequence of zeros as
      # hash.
      base_hashes.append((current_file, hsh))
    current_file = None

# Make sure we found something.
assert base_hashes

# Iterate over the last 1000 commits.
for i in xrange(1000):
  # Translate commit position relative to HEAD to its hash.
  commit_hsh = subprocess.check_output(
      ['git', '-C', CHECKOUT, 'log', '-n1', '--format=%H', 'HEAD~%d' % i]
  ).strip()

  # Iterate over all files of the patch and compare the hashes.
  for f, file_hsh_from_patch in base_hashes:
    file_hsh_from_commit = subprocess.check_output(
        ['git', '-C', CHECKOUT, 'rev-parse', '%s:%s' % (commit_hsh, f)]
    ).strip()
    if not file_hsh_from_commit.startswith(file_hsh_from_patch):
      # Check if file hashes match. The hash from the patch might be an
      # abbreviation.
      print 'Skipping %s as file %s has no matching base.' % (commit_hsh, f)
      break
  else:
    # Loop terminated gracefully, all file hashes matched.
    print 'Found a match: %s' % commit_hsh
    with open(sys.argv[3], 'w') as out_file:
      out_file.write(commit_hsh)
    sys.exit(0)

  if commit_hsh == V8_COVERAGE_SUPPORT_COMMIT:
    print 'The CL is too old, code coverage is not supported. Please rebase.'
    sys.exit(1)

print 'Reached commit limit. Couldn\'t find an appropriate commit.'
sys.exit(1)