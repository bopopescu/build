#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs unit tests on host_info.py.

Usage:
  ./host_info_test.py
"""

import unittest

from subordinate.ios import host_info


class ExtractXcodeVersionTest(unittest.TestCase):
  """Unit tests for host_info.extract_xcode_version."""
  def testEmpty(self):
    inp = [
    ]

    out = [
      None,
      None,
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testVersionOnly(self):
    inp = [
      'Xcode 5.0',
    ]

    out = [
      '5.0',
      None,
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testBuildVersionOnly(self):
    inp = [
      '',
      'Build version 5A1413',
    ]

    out = [
      None,
      '5A1413',
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testVersionAndBuildVersion(self):
    inp = [
      'Xcode 5.0',
      'Build version 5A1413',
    ]

    out = [
      '5.0',
      '5A1413',
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testExtraLines(self):
    inp = [
      'Xcode 5.1',
      'Build version 5B130a',
      '',
      'abc',
    ]

    out = [
      '5.1',
      '5B130a',
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testIndecipherableVersion(self):
    inp = [
      'asdf',
    ]

    out = [
      None,
      None,
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)

  def testIndecipherableBuildVersion(self):
    inp = [
      'Xcode 5.0.2',
      'asdf',
    ]

    out = [
      '5.0.2',
      None,
    ]

    self.assertSequenceEqual(host_info.extract_xcode_version(inp), out)


class ExtractSDKsTest(unittest.TestCase):
  """Unit tests for host_info.extract_sdks."""
  def testEmpty(self):
    inp = [
    ]

    out = [
    ]

    self.assertSequenceEqual(host_info.extract_sdks(inp), out)

  def testOneSDK(self):
    inp = [
      'Mac OS X 10.6 -sdk macosx10.6',
    ]

    out = [
      'macosx10.6',
    ]

    self.assertSequenceEqual(host_info.extract_sdks(inp), out)

  def testSeveralSDKs(self):
    inp = [
      'Simulator - iOS 6.1 -sdk iphonesimulator6.1',
      'Simulator - iOS 7.0 -sdk iphonesimulator7.0',
      'Simulator - iOS 7.1 -sdk iphonesimulator7.1',
    ]

    out = [
      'iphonesimulator6.1',
      'iphonesimulator7.0',
      'iphonesimulator7.1',
    ]

    self.assertSequenceEqual(host_info.extract_sdks(inp), out)

  def testSeveralSDKsSeveralCategories(self):
    inp = [
      'iOS SDKs:',
      'iOS 7.1 -sdk iphoneos7.1',
      'iOS Simulator SDKs:',
      'Simulator - iOS 6.1 -sdk iphonesimulator6.1',
      'Simulator - iOS 7.0 -sdk iphonesimulator7.0',
      'Simulator - iOS 7.1 -sdk iphonesimulator7.1',
    ]

    out = [
      'iphoneos7.1',
      'iphonesimulator6.1',
      'iphonesimulator7.0',
      'iphonesimulator7.1',
    ]

    self.assertSequenceEqual(host_info.extract_sdks(inp), out)


if __name__ == '__main__':
  unittest.main()
