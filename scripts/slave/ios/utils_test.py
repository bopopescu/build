#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs unit tests on utils.py.

Usage:
  ./utils_test.py
"""

# pylint: disable=relative-import
import environment_setup

import mock
import os
import unittest

from subordinate.ios import utils


class GetLinesTest(unittest.TestCase):
  """Unit tests for utils.CallResult._get_lines."""
  def testGetLinesEmptyOutput(self):
    text = ''
    expected = tuple()
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesOneLine(self):
    text = 'one line'
    expected = ('one line',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesTwoLines(self):
    text = 'line one\nline two'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesOneBlankLineInBetween(self):
    text = 'line one\n\nline two'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesTwoBlankLinesInBetween(self):
    text = 'line one\n\n\nline two'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesOneBlankLineAtTheBeginning(self):
    text = '\nline one\nline two'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesTwoBlankLinesAtTheBeginning(self):
    text = '\n\nline one\nline two'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesOneBlankLineAtTheEnd(self):
    text = 'line one\nline two\n'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)

  def testGetLinesTwoBlankLinesAtTheEnd(self):
    text = 'line one\nline two\n\n'
    expected = ('line one', 'line two',)
    self.assertTupleEqual(utils.CallResult._get_lines(text), expected)


class CallTest(unittest.TestCase):
  """Unit tests for utils.call."""
  def setUp(self):
    # Install mocks that consume all output utils.call produces.
    self.stdout = utils.sys.stdout
    self.stderr = utils.sys.stderr
    utils.sys.stdout = mock.Mock()
    utils.sys.stderr = mock.Mock()

    # Install mocks for the objects we're going to test.
    self.patchers = []
    self.patchers.append(mock.patch('subprocess.Popen'))
    self.popen = self.patchers[-1].start()
    self.patchers.append(mock.patch('os.getcwd'))
    self.getcwd = self.patchers[-1].start()

  def tearDown(self):
    # Uninstall any mocks we installed.
    utils.sys.stdout = self.stdout
    utils.sys.stderr = self.stderr

    for patcher in self.patchers:
      patcher.stop()

  def testCallNoArgs(self):
    # Set up mocks and call the method under test.
    self.getcwd.return_value = 'cwd'
    instance = self.popen.return_value
    instance.communicate.return_value = 'out', 'err'
    instance.returncode = 123
    cr = utils.call('binary',)

    # Assert os.getcwd was called exactly once, without arguments.
    self.getcwd.assert_called_once()
    self.failIf(self.getcwd.call_args[0])
    self.failIf(self.getcwd.call_args[1])

    # Assert exactly one Popen was created, with correct arguments.
    self.popen.assert_called_once()
    popen_args = self.popen.call_args_list[0][0]
    popen_kwargs = self.popen.call_args_list[0][1]
    self.assertEqual(len(popen_args), 1)
    self.assertSequenceEqual(popen_args[0], ['binary'])
    self.assertDictEqual(popen_kwargs, {
      'stdout': utils.subprocess.PIPE,
      'stderr': utils.subprocess.PIPE,
    })

    # Assert Popen.communicate was called exactly once, without arguments.
    instance.communicate.assert_called_once()
    self.failIf(instance.communicate.call_args[0])
    self.failIf(instance.communicate.call_args[1])

    # Assert the returned CallResult struct is correct.
    self.assertEqual(cr.returncode, 123)
    self.assertTupleEqual(cr.stdout, ('out',))
    self.assertTupleEqual(cr.stderr, ('err',))

  def testCallOneArg(self):
    # Set up mocks and call the method under test.
    self.getcwd.return_value = 'cwd'
    instance = self.popen.return_value
    instance.communicate.return_value = 'line 1\nline 2', 'line 3\nline 4'
    instance.returncode = 456
    cr = utils.call('bin', 'arg')

    # Assert os.getcwd was called exactly once, without arguments.
    self.getcwd.assert_called_once()
    self.failIf(self.getcwd.call_args[0])
    self.failIf(self.getcwd.call_args[1])

    # Assert exactly one Popen was created, with correct arguments.
    self.popen.assert_called_once()
    popen_args = self.popen.call_args_list[0][0]
    popen_kwargs = self.popen.call_args_list[0][1]
    self.assertEqual(len(popen_args), 1)
    self.assertSequenceEqual(popen_args[0], ['bin', 'arg'])
    self.assertDictEqual(popen_kwargs, {
      'stdout': utils.subprocess.PIPE,
      'stderr': utils.subprocess.PIPE,
    })

    # Assert Popen.communicate was called exactly once, without arguments.
    instance.communicate.assert_called_once()
    self.failIf(instance.communicate.call_args[0])
    self.failIf(instance.communicate.call_args[1])

    # Assert the returned CallResult struct is correct.
    self.assertEqual(cr.returncode, 456)
    self.assertTupleEqual(cr.stdout, ('line 1', 'line 2'))
    self.assertTupleEqual(cr.stderr, ('line 3', 'line 4'))

  def testCallSeveralArgs(self):
    # Set up mocks and call the method under test.
    self.getcwd.return_value = 'cwd'
    instance = self.popen.return_value
    instance.communicate.return_value = 'line 1\nline 2', 'line 3\nline 4'
    instance.returncode = 789
    cr = utils.call('bin', 'arg 0', 'arg 1', 'arg 2')

    # Assert os.getcwd was called exactly once, without arguments.
    self.getcwd.assert_called_once()
    self.failIf(self.getcwd.call_args[0])
    self.failIf(self.getcwd.call_args[1])

    # Assert exactly one Popen was created, with correct arguments.
    self.popen.assert_called_once()
    popen_args = self.popen.call_args_list[0][0]
    popen_kwargs = self.popen.call_args_list[0][1]
    self.assertEqual(len(popen_args), 1)
    self.assertSequenceEqual(popen_args[0], ['bin', 'arg 0', 'arg 1', 'arg 2'])
    self.assertDictEqual(popen_kwargs, {
      'stdout': utils.subprocess.PIPE,
      'stderr': utils.subprocess.PIPE,
    })

    # Assert Popen.communicate was called exactly once, without arguments.
    instance.communicate.assert_called_once()
    self.failIf(instance.communicate.call_args[0])
    self.failIf(instance.communicate.call_args[1])

    # Assert the returned CallResult struct is correct.
    self.assertEqual(cr.returncode, 789)
    self.assertTupleEqual(cr.stdout, ('line 1', 'line 2'))
    self.assertTupleEqual(cr.stderr, ('line 3', 'line 4'))


class GTestResult(unittest.TestCase):
  """Unit tests for utils.GTestResult."""
  def testRequiresNonEmptyCommand(self):
    self.assertRaises(ValueError, utils.GTestResult, None)
    self.assertRaises(ValueError, utils.GTestResult, [])

  def testMakesCommandTuple(self):
    self.assertTupleEqual(utils.GTestResult(['command']).command, ('command',))

  def testCanModifyDictsUntilFinalized(self):
    gtest_result = utils.GTestResult(['bin', 'arg'])
    self.failIf(gtest_result.failed_tests)
    self.failIf(gtest_result.flaked_tests)
    self.failIf(gtest_result.passed_tests)
    self.failIf(gtest_result.perf_links)
    self.failUnless(gtest_result.return_code is None)
    self.failUnless(gtest_result.success is None)

    def modify_command():
      gtest_result.command = 'asdf'

    def modify_return_code():
      gtest_result.return_code = 123

    def modify_success():
      gtest_result.success = 'abc'

    self.assertRaises(AttributeError, modify_command)
    self.assertRaises(AttributeError, modify_return_code)
    self.assertRaises(AttributeError, modify_success)

    gtest_result.failed_tests['test 1'] = ['line 1', 'line 2']
    self.assertEqual(len(gtest_result.failed_tests), 1)
    self.assertTrue('test 1' in gtest_result.failed_tests)
    self.assertListEqual(
      gtest_result.failed_tests['test 1'], ['line 1', 'line 2'])

    gtest_result.flaked_tests['test A'] = ['line A', 'line B']
    self.assertEqual(len(gtest_result.flaked_tests), 1)
    self.assertTrue('test A' in gtest_result.flaked_tests)
    self.assertListEqual(
      gtest_result.flaked_tests['test A'], ['line A', 'line B'])

    gtest_result.passed_tests.append('test 1')
    gtest_result.passed_tests.append('test 2')
    self.assertListEqual(gtest_result.passed_tests, ['test 1', 'test 2'])

    gtest_result.perf_links['trace 1'] = 'https://chromeperf.appspot.com'
    self.assertEqual(len(gtest_result.perf_links), 1)
    self.assertEqual(
      gtest_result.perf_links['trace 1'], 'https://chromeperf.appspot.com')

    gtest_result.finalize(0, True)
    self.assertEqual(gtest_result.return_code, 0)
    self.assertTrue(gtest_result.success)

    # After finalization, we get a deepcopy back, so we can no longer
    # modify gtest_result.failed_tests, gtest_result.flaked_tests,
    # gtest_result.passed_tests, or gtest_result.perf_links.

    gtest_result.failed_tests['test 1'].append('line 3')
    gtest_result.failed_tests['test 2'] = ['line 4', 'line 5']
    self.assertEqual(len(gtest_result.failed_tests), 1)
    self.assertTrue('test 1' in gtest_result.failed_tests)
    self.assertListEqual(
      gtest_result.failed_tests['test 1'], ['line 1', 'line 2'])

    gtest_result.flaked_tests['test A'].append('line C')
    gtest_result.flaked_tests['test B'] = ['line D', 'line E']
    self.assertEqual(len(gtest_result.flaked_tests), 1)
    self.assertTrue('test A' in gtest_result.flaked_tests)
    self.assertListEqual(
      gtest_result.flaked_tests['test A'], ['line A', 'line B'])

    gtest_result.passed_tests.append('test 3')
    gtest_result.passed_tests.append('test 4')
    self.assertListEqual(gtest_result.passed_tests, ['test 1', 'test 2'])

    gtest_result.perf_links['trace 1'] = 'localhost'
    gtest_result.perf_links['trace 2'] = 'example.com'
    gtest_result.perf_links['trace 1'] = 'https://chromeperf.appspot.com'
    self.assertEqual(len(gtest_result.perf_links), 1)
    self.assertEqual(
      gtest_result.perf_links['trace 1'], 'https://chromeperf.appspot.com')


class GTestTest(unittest.TestCase):
  """Unit tests for utils.gtest."""
  def setUp(self):
    # Install mocks that consume all output gtest produces.
    self.stdout = utils.sys.stdout
    self.stderr = utils.sys.stderr
    utils.sys.stdout = mock.Mock()
    utils.sys.stderr = mock.Mock()

    # Install mocks for the objects we're going to test.
    self.patchers = []
    self.patchers.append(mock.patch('subprocess.Popen'))
    self.popen = self.patchers[-1].start()
    self.patchers.append(mock.patch('utils.gtest_utils.GTestLogParser'))
    self.parser = self.patchers[-1].start()

  def tearDown(self):
    # Uninstall any mocks we installed.
    utils.sys.stdout = self.stdout
    utils.sys.stderr = self.stderr

    for patcher in self.patchers:
      patcher.stop()

  def testGTest(self):
    # Set up mocks and call the method under test.
    popen_instance = self.popen.return_value
    popen_instance.returncode = 10101
    popen_instance.stdout.readline.return_value = ''
    parser_instance = self.parser.return_value
    parser_instance.CompletedWithoutFailure.return_value = True
    self.assertTrue(utils.gtest(['command']).success)

    # Assert exactly one Popen was created, with correct arguments.
    self.popen.assert_called_once()
    popen_args = self.popen.call_args_list[0][0]
    popen_kwargs = self.popen.call_args_list[0][1]
    self.assertEqual(len(popen_args), 1)
    self.assertSequenceEqual(popen_args[0], ['command'])
    self.assertDictEqual(popen_kwargs, {
      'stdout': utils.subprocess.PIPE,
      'stderr': utils.subprocess.STDOUT,
    })

    # Assert exactly one GTestLogParser was created, without arguments.
    self.parser.assert_called_once()
    self.failIf(self.parser.call_args[0])
    self.failIf(self.parser.call_args[1])

    # Assert Popen.wait was called exactly once, without arguments.
    popen_instance.wait.assert_called_once()
    self.failIf(popen_instance.wait.call_args[0])
    self.failIf(popen_instance.wait.call_args[1])

    # Assert parser.CompletedWithoutFailure was called exactly once,
    # without arguments.
    parser_instance.CompletedWithoutFailure.assert_called_once()
    self.failIf(parser_instance.CompletedWithoutFailure.call_args[0])
    self.failIf(parser_instance.CompletedWithoutFailure.call_args[1])


if __name__ == '__main__':
  unittest.main()
