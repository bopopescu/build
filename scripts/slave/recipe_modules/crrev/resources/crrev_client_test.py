#!/usr/bin/python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..'))
import common.env
common.env.Install()

import mock
import requests

import crrev_client  # pylint: disable=relative-import


@mock.patch('requests.get')
class CrrevClientTest(unittest.TestCase):

  def test_main(self, mock_get):
    mock_response = mock.MagicMock()
    response_data = {
        'git_sha': 'e91f8875e590ddf00af267062fc1a9ec48658373',
        'numbering_type': 'COMMIT_POSITION'
    }
    mock_response.text = json.dumps(response_data)
    mock_get.return_value = mock_response
    output = crrev_client.main([
        'get_numbering',
        '--params-file=test_params_file.json',
    ])
    self.assertEqual(json.dumps(response_data, indent=2), output)
    self.assertEqual(mock_get.call_count, 1)

  def test_simple_get(self, mock_get):
    mock_response = mock.MagicMock()
    response_data = {
        'git_sha': 'e91f8875e590ddf00af267062fc1a9ec48658373',
        'numbering_type': 'COMMIT_POSITION'
    }
    mock_response.text = json.dumps(response_data)
    mock_get.return_value = mock_response
    params = [
        ('number', '375953'),
        ('numbering_identifier', 'refs/heads/main'),
        ('numbering_type', 'COMMIT_POSITION'),
        ('project', 'chromium'),
        ('repo', 'chromium/src'),
        ('fields', 'git_sha,numbering_type'),
    ]
    self.assertEqual(
        response_data,
        crrev_client.crrev_get('get_numbering', params=params, attempts=3))
    mock_get.assert_called_once_with(
        'https://cr-rev.appspot.com/_ah/api/crrev/v1/get_numbering'
        '?number=375953'
        '&numbering_identifier=refs%2Fheads%2Fmain'
        '&numbering_type=COMMIT_POSITION'
        '&project=chromium'
        '&repo=chromium%2Fsrc'
        '&fields=git_sha%2Cnumbering_type',
        verify=True)

  def test_404(self, mock_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    with self.assertRaises(ValueError):
      crrev_client.crrev_get('redirect/123456', params={}, attempts=1)

  @mock.patch('crrev_client.time.sleep', mock.MagicMock())
  @mock.patch('crrev_client.logging.exception', mock.MagicMock())
  def test_retry(self, mock_get):
    mock_get.side_effect = requests.RequestException
    with self.assertRaises(requests.RequestException):
      crrev_client.crrev_get('redirect/123456', params={}, attempts=3)
    self.assertEqual(3, mock_get.call_count)


if __name__ == '__main__':
  unittest.main()

