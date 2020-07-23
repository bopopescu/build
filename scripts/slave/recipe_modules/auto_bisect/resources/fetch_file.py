#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gets the text content of a file in the Chromium repo using gitiles.

Example usage:
  ./fetch_file.py DEPS
"""

import argparse
import base64
import binascii
import urllib2

_URL_TEMPLATE = ('https://chromium.googlesource.com/%s/+/%s/%s'
                 '?format=TEXT')


def fetch_file(repo, commit, path):
  """Fetches the contents of a file using gitiles.

  Args:
    path: The path relative to the root of the repository.
    repo: The name of the repo on chromium.googlesource.com, e.g. chromium/src.
    commit: The commit at which to look at the file, e.g. main or git hash.

  Returns:
    The text of the file as a string.

  Raises:
    urllib2.HTTPError: There was an error when making the request.
    binascii.Error: There was an error decoding the response.
  """
  url = _URL_TEMPLATE % (repo, commit, path)
  encoded_content = urllib2.urlopen(url).read()
  return base64.decodestring(encoded_content)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('path')
  parser.add_argument('--repo', default='chromium/src')
  parser.add_argument('--commit', default='main')
  args = parser.parse_args()
  print fetch_file(args.repo, args.commit, args.path)


if __name__ == '__main__':
  main()
