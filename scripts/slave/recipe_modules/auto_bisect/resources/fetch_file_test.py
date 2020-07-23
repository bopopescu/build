#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import os
import sys
import unittest

_BUILD_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir,
    os.path.pardir, os.path.pardir, os.path.pardir))
sys.path.insert(0, os.path.join(_BUILD_PATH, 'third_party', 'mock-1.0.1'))

import mock

import fetch_file  # pylint: disable=relative-import

_TEST_DATA = os.path.join(os.path.dirname(__file__), 'test_data')


@mock.patch('urllib2.urlopen')
class CommitPositionTest(unittest.TestCase):

  def test_fetch_file(self, mock_urlopen):
    file_like_object = mock.MagicMock()
    file_like_object.read = mock.MagicMock(
        return_value=base64.b64encode('some contents'))
    mock_urlopen.return_value = file_like_object
    self.assertEqual(
        'some contents',
        fetch_file.fetch_file('chromium/src', 'main', 'some/path'))
    mock_urlopen.assert_called_once_with(
        'https://chromium.googlesource.com'
        '/chromium/src/+/main/some/path?format=TEXT')


if __name__ == '__main__':
  unittest.main()
