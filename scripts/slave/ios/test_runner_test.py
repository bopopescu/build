#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs unit tests on test_runner.py.

Usage:
  ./test_runner_test.py
"""

# pylint: disable=relative-import
import environment_setup

import mock
import os
import tempfile
import unittest

from subordinate.ios import test_runner

class TestRunnerTest(unittest.TestCase):
  """Unit tests for test_runner.TestRunner."""

  def testRaisesAppNotFoundError(self):
    """Ensures invalid app_path raises AppNotFoundError."""
    self.assertRaises(
      test_runner.AppNotFoundError, test_runner.TestRunner, '/tmp/fakepath')

  def testRaisesUnexpectedAppExtensionError(self):
    """Ensures invalid app_path raises UnexpectedAppExtensionError."""
    self.assertRaises(
      test_runner.UnexpectedAppExtensionError,
      test_runner.TestRunner,
      tempfile.mkdtemp(),
    )

  def testDoesNotRaiseAppNotFoundError(self):
    """Ensures valid app_path does not raise AppNotFoundError."""
    self.failUnless(test_runner.TestRunner(tempfile.mkdtemp('.app')))
    self.failUnless(test_runner.TestRunner(tempfile.mkdtemp('.ipa')))

  def testRequireTearDown(self):
    """Ensures methods decorated with RequireTearDown call TearDown last."""
    class TearDownTestRunner(test_runner.TestRunner):
      def __init__(self):
        super(TearDownTestRunner, self).__init__(tempfile.mkdtemp('.ipa'))
        self.values = []

      def TearDown(self):
        self.values.append('teardown')

      def GetLaunchCommand(self, test_filter=None, blacklist=None):
        pass

      def Launch(self):
        pass

      def NoTearDown(self, value):
        self.values.append(value)

      @test_runner.TestRunner.RequireTearDown
      def RequiresTearDown(self, value):
        self.values.append(value)

      @test_runner.TestRunner.RequireTearDown
      def ExceptionRaiser(self):
        raise NotImplementedError

    t = TearDownTestRunner()
    self.failIf(t.values)

    t.NoTearDown('abc')
    self.assertListEqual(t.values, ['abc'])

    t.RequiresTearDown('123')
    self.assertListEqual(t.values, ['abc', '123', 'teardown'])

    self.assertRaises(NotImplementedError, t.ExceptionRaiser)
    self.assertListEqual(t.values, ['abc', '123', 'teardown', 'teardown'])

  def testGetFilter(self):
    """Tests the results of GetGTestFilter and GetKIFTestFilter."""
    tests = [
      'Test 1',
      'Test 2',
      'KIF.Test A',
      'KIF.Test B',
    ]

    expected_gtest = 'Test 1:Test 2:KIF.Test A:KIF.Test B'
    expected_inverted_gtest = '-Test 1:Test 2:KIF.Test A:KIF.Test B'
    expected_kif = 'NAME:Test 1|Test 2|Test A|Test B'
    expected_inverted_kif = '-NAME:Test 1|Test 2|Test A|Test B'

    self.assertEqual(
      test_runner.TestRunner.GetGTestFilter(tests, False),
      expected_gtest,
    )
    self.assertEqual(
      test_runner.TestRunner.GetGTestFilter(tests, True),
      expected_inverted_gtest,
    )
    self.assertEqual(
      test_runner.TestRunner.GetKIFTestFilter(tests, False),
      expected_kif,
    )
    self.assertEqual(
      test_runner.TestRunner.GetKIFTestFilter(tests, True),
      expected_inverted_kif,
    )


class SimulatorTestRunnerTest(unittest.TestCase):
  """Unit tests for test_runner.SimulatorTestRunner."""
  def testRaisesSimulatorNotFoundError(self):
    """Ensures SimulatorNotFoundError is raised when iossim doesn't exist."""
    self.assertRaises(
      test_runner.SimulatorNotFoundError,
      test_runner.SimulatorTestRunner,
      tempfile.mkdtemp('.app'),
      '/tmp/fake/path/to/iossim',
      'iPhone 5',
      '8.0',
    )


if __name__ == '__main__':
  unittest.main()
