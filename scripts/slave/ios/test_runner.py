#!/usr/bin/python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains test runners for launching tests on simulators and devices."""

# pylint: disable=relative-import
import environment_setup

import collections
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from common import gtest_utils
from subordinate import subordinate_utils
from subordinate.ios import find_xcode
from subordinate.ios import utils


class Error(Exception):
  pass


class TestRunnerError(Error):
  pass


class AppNotFoundError(TestRunnerError):
  """The app intended to be run was not found."""
  def __init__(self, app_path):
    super(AppNotFoundError, self).__init__(
      'App does not exist: %s.' % app_path
    )


class XcodeVersionNotFoundError(TestRunnerError):
  """The Xcode version intended to be used was not found."""
  def __init__(self, xcode_version):
    super(XcodeVersionNotFoundError, self).__init__(
      'Xcode with the specified version not found: %s.' % xcode_version
    )


class UnexpectedAppExtensionError(TestRunnerError):
  """The app had an unexpected or no extension."""
  def __init__(self, app_path, valid_extensions):
    if not valid_extensions:
      valid_extensions = 'Expected no extension.'
    elif len(valid_extensions) == 1:
      valid_extensions = 'Expected extension: %s.' % valid_extensions[0]
    else:
      valid_extensions = 'Expected extension to be one of %s.' % ', '.join(
        extension for extension in valid_extensions)

    super(UnexpectedAppExtensionError, self).__init__(
      'Unexpected app path: %s. %s' % (app_path, valid_extensions))


class SimulatorNotFoundError(TestRunnerError):
  """The iossim path was not found."""
  def __init__(self, iossim_path):
    super(SimulatorNotFoundError, self).__init__(
      'Simulator does not exist: %s.' % iossim_path)


class AppLaunchError(TestRunnerError):
  """There was an error launching the app."""
  pass


class TestRunner(object):
  """Base class containing common TestRunner functionality."""
  def __init__(
    self,
    app_path,
    xcode_version=None,
    gs_bucket=None,
    perf_bot_name=None,
    perf_build_number=None,
    perf_builder_name=None,
    perf_main_name=None,
    perf_revision=None,
    perf_x_value=None,
    test_args=None,
  ):
    """Initializes a new instance of the TestRunner class.

    Args:
      app_path: Full path to the compiled app to run.
      xcode_version: Version of Xcode to use.
      gs_bucket: Google Storage bucket to upload test data to, or None if the
        test data should not be uploaded.
      perf_bot_name: Name of this bot as indicated to the perf dashboard.
      perf_build_number: Build number to indicate to the perf dashboard.
      perf_builder_name: Name of this builder as indicated to the perf
        dashboard.
      perf_main_name: Name of the main as indicated to the perf dashboard.
      perf_revision: Revision to indicate to the perf dashboard.
      perf_x_value: Value to use on the x axis for all data uploaded to the
      perf dashboard.
      test_args: Arguments to pass when launching the test.

    Raises:
      AppNotFoundError: If the specified app cannot be found.
      UnexpectedAppExtensionError: If the app was not an .app or an .ipa.
    """
    if not os.path.exists(app_path):
      raise AppNotFoundError(app_path)

    self.app_path = app_path
    self.app_name, ext = os.path.splitext(os.path.split(app_path)[1])

    if ext not in ('.app', '.ipa'):
      raise UnexpectedAppExtensionError(app_path, ['.app', '.ipa'])

    if xcode_version is not None:
      xcode_summary = find_xcode.find_xcode(xcode_version)

      if not xcode_summary['found']:
        raise XcodeVersionNotFoundError(xcode_version)

    self.gs_bucket = gs_bucket
    self.perf_bot_name = perf_bot_name
    self.perf_main_name = perf_main_name
    self.perf_revision = perf_revision
    self.perf_build_number = perf_build_number
    self.perf_builder_name = perf_builder_name
    self.perf_x_value = perf_x_value
    self.test_args = test_args or []

    self.summary = {
      'links': collections.OrderedDict(),
      'logs': collections.OrderedDict(),
    }

  @staticmethod
  def Print(message, blank_lines=0, time_to_sleep=0):
    """Prints a message.

    Args:
      message: The message to print.
      blank_lines: The number of blank lines to leave after the message.
      time_to_sleep: The number of seconds to wait after printing the message.
    """
    print '%s%s' % (message, ''.join(['\n' for _ in xrange(blank_lines)]))
    sys.stdout.flush()

    if time_to_sleep:
      time.sleep(time_to_sleep)

  def TearDown(self):
    """Performs post-test tear down."""
    raise NotImplementedError

  @staticmethod
  def RequireTearDown(method):
    """Ensures TearDown is called after calling the specified method.

    This decorator can be used to ensure that the tear down logic executes
    regardless of how the decorated method exits.

    Args:
      method: The method to require a tear down for.
    """
    def TearDownMethodCall(self, *args, **kwargs):
      try:
        return method(self, *args, **kwargs)
      finally:
        self.TearDown()
    return TearDownMethodCall

  @staticmethod
  def GetKIFTestFilter(tests, blacklist):
    """Returns the KIF test filter to run or exclude only the given tests.

    Args:
      tests: The list of tests to run or exclude.
      blacklist: Whether to run all except the given tests or not.

    Returns:
      A string which can be supplied to GKIF_SCENARIO_FILTER.
    """
    if blacklist:
      blacklist = '-'
    else:
      blacklist = ''

    # For KIF tests, a pipe-separated list of tests will run just those tests.
    # However, we also need to remove the "KIF." prefix from these tests.
    # Using a single minus ahead of NAME will instead run everything other than
    # the listed tests.
    return '%sNAME:%s' % (
      blacklist,
      '|'.join(test.split('KIF.', 1)[-1] for test in tests),
    )

  @staticmethod
  def GetGTestFilter(tests, blacklist):
    """Returns the GTest filter to run or exclude only the given tests.

    Args:
      tests: The list of tests to run or exclude.
      blacklist: Whether to run all except the given tests or not.

    Returns:
      A string which can be supplied to --gtest_filter.
    """
    if blacklist:
      blacklist = '-'
    else:
      blacklist = ''

    # For GTests, a colon-separated list of tests will run just those tests.
    # Using a single minus at the beginning will instead run everything other
    # than the listed tests.
    return '%s%s' % (blacklist, ':'.join(test for test in tests))

  def GetLaunchCommand(self, test_filter=None, blacklist=False):
    """Returns the command which is used to launch the test.

    Args:
      test_filter: A list of tests to filter by, or None to mean all.
      blacklist: Whether to blacklist the elements of test_filter or not. Only
        works when test_filter is not None.

    Returns:
      A list whose elements are the args representing the command.
    """
    raise NotImplementedError

  @staticmethod
  def _Run(command):
    """Runs the specified command, parsing GTest output.

    Args:
      command: The shell command to execute, as a list of arguments.

    Returns:
      A GTestResult instance.
    """
    result = utils.GTestResult(command)

    print ' '.join(command)
    print 'cwd:', os.getcwd()
    sys.stdout.flush()

    proc = subprocess.Popen(
      command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    parser = gtest_utils.GTestLogParser()

    while True:
      line = proc.stdout.readline()
      if not line:
        break
      line = line.rstrip()
      parser.ProcessLine(line)
      print line
      sys.stdout.flush()

    proc.wait()

    for test in parser.FailedTests(include_flaky=True):
      # Tests are named as TestCase.TestName.
      # A TestName starting with FLAKY_ should not turn the build red.
      if '.' in test and test.split('.', 1)[1].startswith('FLAKY_'):
        result.flaked_tests[test] = parser.FailureDescription(test)
      else:
        result.failed_tests[test] = parser.FailureDescription(test)

    result.passed_tests.extend(parser.PassedTests(include_flaky=True))

    print command[0], 'returned', proc.returncode
    print
    sys.stdout.flush()

    # iossim can return 5 if it exits noncleanly, even if no tests failed.
    # Therefore we can't rely on this exit code to determine success or failure.
    result.finalize(proc.returncode, parser.CompletedWithoutFailure())
    return result

  def Launch(self):
    """Launches the test."""
    raise NotImplementedError

  def RunAllTests(self, result, *args, **kwargs):
    """Ensures all tests run, even if any crash the test app.

    Args:
      result: A GTestResult instance from having run the app.

    Returns:
      True if all tests were successful on the initial run.

    Raises:
      AppLaunchError: If the given result had crashed.
    """
    if result.crashed and not result.crashed_test:
      # If the app crashed without even starting, give up.
      raise AppLaunchError

    failed_tests = result.failed_tests
    flaked_tests = result.flaked_tests
    passed_tests = result.passed_tests
    perf_links = result.perf_links

    try:
      while (result.crashed
             and result.crashed_test
             and not kwargs.get('retries')):
        # If the app crashed on a specific test, then resume at the next test,
        # except when 'retries' is nonzero. The 'retries' kwarg already forces
        # the underlying gtest call to retry a fixed amount of times, and we
        # don't want to conflict with this, because stability and memory tests
        # rely on this behavior to run the same test on successive URLs.
        self.Print(
          '%s appears to have crashed during %s. Resuming at next test...' % (
            self.app_name, result.crashed_test,
           ), blank_lines=2, time_to_sleep=5)

        # Now run again, filtering out every test that ran. This is equivalent
        # to starting at the next test.
        result = self._Run(self.GetLaunchCommand(
          test_filter=passed_tests + failed_tests.keys() + flaked_tests.keys(),
          blacklist=True,
        ), *args, **kwargs)

        # We are never overwriting any old data, because we aren't running any
        # tests twice here.
        failed_tests.update(result.failed_tests)
        flaked_tests.update(result.flaked_tests)
        passed_tests.extend(result.passed_tests)
        perf_links.update(result.perf_links)

      if failed_tests and not result.crashed and not kwargs.get('retries'):
        # If the app failed without crashing, retry the failed tests in case of
        # flake, except when 'retries' is nonzero.
        msg = ['The following tests appear to have failed:']
        msg.extend(failed_tests.keys())
        msg.append('These tests will be retried, but their retry results will'
                   ' not affect the outcome of this test step.')
        msg.append('Retry results are purely for informational purposes.')
        msg.append('Retrying...')
        self.Print('\n'.join(msg), blank_lines=2, time_to_sleep=5)

        self._Run(self.GetLaunchCommand(
          test_filter=failed_tests.keys(),
        ), *args, **kwargs)
    except OSError as e:
      if e.errno == errno.E2BIG:
        self.Print(
          'Too many tests were found in this app to resume.',
          blank_lines=1,
          time_to_sleep=0,
        )
      else:
        self.Print(
          'Unexpected OSError: %s.' % e.errno, blank_lines=1, time_to_sleep=0)

    self.InterpretResult(failed_tests, flaked_tests, passed_tests, perf_links)

    # At this point, all the tests have run, so used failed_tests to determine
    # the success/failure.
    return not failed_tests

  def InterpretResult(self, failed_tests, flaked_tests, passed_tests,
                      perf_links):
    """Interprets the given GTestResult.

    Args:
      failed_tests: A dict of failed test names mapping to lines of output.
      flaked_tests: A dict of failed flaky test names mapping to lines of
        output.
      passed_tests: A list of passed test names.
      perf_links: A dict of trace names mapping to perf dashboard URLs.
    """
    for test, log_lines in failed_tests.iteritems():
      self.summary['logs'][test] = log_lines

    for test, log_lines in flaked_tests.iteritems():
      self.summary['logs'][test] = log_lines

    for test in passed_tests:
      self.summary['logs']['passed tests'] = passed_tests

    for trace, graph_url in perf_links.iteritems():
      self.summary['links'][trace] = graph_url


class SimulatorTestRunner(TestRunner):
  """Class for running a test app on an iOS simulator."""
  def __init__(
    self,
    app_path,
    iossim_path,
    platform,
    version,
    xcode_version=None,
    gs_bucket=None,
    perf_bot_name=None,
    perf_build_number=None,
    perf_builder_name=None,
    perf_main_name=None,
    perf_revision=None,
    perf_x_value=None,
    test_args=None,
  ):
    """Initializes an instance of the SimulatorTestRunner class.

    Args:
      app_path: Full path to the compiled app to run.
      iossim_path: Full path to the iossim executable to launch.
      platform: The platform to simulate. Supported values can be found by
        running 'iossim -l'. e.g. 'iPhone 5', 'iPhone 5s'.
      version: The iOS version the simulator should be running. Supported values
        can be found by running 'iossim -l'. e.g. '8.0', '7.1'.
      xcode_version: Version of Xcode to use.
      gs_bucket: Google Storage bucket to upload test data to, or None if the
        test data should not be uploaded.
      perf_bot_name: Name of this bot as indicated to the perf dashboard.
      perf_build_number: Build number to indicate to the perf dashboard.
      perf_builder_name: Name of this builder as indicated to the perf
        dashboard.
      perf_main_name: Name of the main as indicated to the perf dashboard.
      perf_revision: Revision to indicate to the perf dashboard.
      perf_x_value: Value to use on the x axis for all data uploaded to the
      perf dashboard.
      test_args: Arguments to pass when launching the test.

    Raises:
      SimulatorNotFoundError: If the given iossim path cannot be found.
    """
    super(SimulatorTestRunner, self).__init__(
      app_path,
      xcode_version=xcode_version,
      gs_bucket=gs_bucket,
      perf_bot_name=perf_bot_name,
      perf_build_number=perf_build_number,
      perf_builder_name=perf_builder_name,
      perf_main_name=perf_main_name,
      perf_revision=perf_revision,
      perf_x_value=perf_x_value,
      test_args=test_args,
    )

    if not os.path.exists(iossim_path):
      raise SimulatorNotFoundError(iossim_path)

    self.cfbundleid = utils.call(
      utils.PLIST_BUDDY,
      '-c', 'Print:CFBundleIdentifier',
      os.path.join(self.app_path, 'Info.plist'),
    ).stdout[0]

    self.iossim_path = iossim_path
    self.platform = platform
    self.version = version
    self.timeout = '120'
    self.homedir = ''
    self.start_time = None

  def SetStartTime(self):
    """Sets the start time, for finding crash reports during this run."""
    # Crash reports have a timestamp in their filename, formatted as
    # YYYY-MM-DD-HHMMSS.
    self.start_time = time.strftime('%Y-%m-%d-%H%M%S', time.localtime())

  def CreateNewHomeDirectory(self):
    """Creates a new home directory for the simulator."""
    self.homedir = tempfile.mkdtemp()

  def RemoveHomeDirectory(self):
    """Recursively removes the home directory being used by the simulator."""
    if os.path.exists(self.homedir):
      shutil.rmtree(self.homedir, ignore_errors=True)
      self.homedir = ''

  def KillSimulators(self):
    """Forcibly kills any running iOS simulator instances."""
    kill_cmd = [
      'pkill',
      '-9',
      '-x',
      # The iOS simulator has a different name depending on the Xcode version.
      'iPhone Simulator',  # Xcode 5
      'iOS Simulator',  # Xcode 6
      'Simulator',  # Xcode 7
    ]

    # If a signal was sent, wait for the simulator to actually be killed.
    if not utils.call(*kill_cmd).returncode:
      time.sleep(5)

  def SetUp(self):
    self.KillSimulators()
    self.CreateNewHomeDirectory()
    self.SetStartTime()

  def TearDown(self):
    """Forcibly kills any running iOS simulator instances."""
    self.UploadTestData()
    self.GetCrashReports()
    self.KillSimulators()
    self.RemoveHomeDirectory()

  def FindTestDocumentsDirectory(self, apps_dir):
    """Finds the test's Documents directory in the given Applications directory.

    Args:
      apps_dir: The Applications directory, containing app ID directories.

    Returns:
      The Documents directory, or None if it doesn't exist.
    """
    for appid_dir in os.listdir(apps_dir):
      appid_dir = os.path.join(apps_dir, appid_dir)
      app_bundle = os.path.join(appid_dir, '%s.app' % self.app_name)
      metadata_plist = os.path.join(
        appid_dir, '.com.apple.mobile_container_manager.metadata.plist')
      docs_dir = os.path.join(appid_dir, 'Documents')

      if os.path.exists(docs_dir):
        # iOS 7 app ID directories contain the app bundle. iOS 8 app ID
        # directories contain a metadata plist with the CFBundleIdentifier.
        if os.path.exists(app_bundle):
          return docs_dir
        elif os.path.exists(metadata_plist) and utils.call(
          utils.PLIST_BUDDY,
          '-c', 'Print:MCMMetadataIdentifier',
          metadata_plist,
        ).stdout[0] == self.cfbundleid:
          return docs_dir

    self.Print('Could not find %s on the simulator.' % self.app_name)

  def UploadTestData(self):
    """Uploads the contents of the test's Documents directory.

    Returns:
      True if test data was uploaded, False otherwise.
    """
    if not self.gs_bucket:
      return False

    apps_dir = ''

    # [homedir]/Library/Developers/CoreSimulator/Devices contains UDID
    # directories for each simulated platform started with this home directory.
    # We'd expect just one such directory since we generate a unique home
    # directory for each SimulatorTestRunner instance. Inside the device
    # UDID directory is where we find the Applications directory.
    udid_dir = os.path.join(
      self.homedir,
      'Library',
      'Developer',
      'CoreSimulator',
      'Devices',
    )

    if os.path.exists(udid_dir):
      udids = os.listdir(udid_dir)

      if len(udids) == 1:
        apps_dir = os.path.join(
          udid_dir,
          udids[0],
          'data',
        )

        if self.version.startswith('7'):
          # On iOS 7 the Applications directory is found right here.
          apps_dir = os.path.join(apps_dir, 'Applications')
        else:
          # On iOS 8+ the Application (singular) directory is a little deeper.
          apps_dir = os.path.join(
            apps_dir,
            'Containers',
            'Data',
            'Application',
          )
      else:
        self.Print(
          'Unexpected number of simulated device UDIDs in %s.' % udid_dir
        )

    docs_dir = None

    if os.path.exists(apps_dir):
      self.Print('Found Applications directory.')
      docs_dir = self.FindTestDocumentsDirectory(apps_dir)

    if docs_dir is not None and os.path.exists(docs_dir):
      subprocess.check_call([
        'screencapture',
        os.path.join(docs_dir, 'desktop.png'),
      ])

      self.summary['links']['test data'] = subordinate_utils.ZipAndUpload(
        self.gs_bucket,
        '%s.zip' % self.app_name,
        docs_dir,
      )

      summary = os.path.join(docs_dir, 'summary.json')
      if os.path.exists(summary):
        self.HandleJsonFileWithPath(summary)

      shutil.rmtree(docs_dir, ignore_errors=True)
      return True

    return False

  def HandleJsonFileWithPath(self, summary):
    """Parse data in summarydir and send to perf dashboard."""
    with open(summary) as jsonFile:
      return json.load(jsonFile)

  def GetCrashReports(self):
    # A crash report's naming scheme is [app]_[timestamp]_[hostname].crash.
    # e.g. net_unittests_2014-05-13-150900_vm1-a1.crash.
    crash_reports_dir = os.path.expanduser(os.path.join(
      '~',
      'Library',
      'Logs',
      'DiagnosticReports',
    ))

    if os.path.exists(crash_reports_dir):
      for crash_report in os.listdir(crash_reports_dir):
        report_name, ext = os.path.splitext(crash_report)

        if report_name.startswith(self.app_name) and ext == '.crash':
          report_time = report_name[len(self.app_name) + 1:].split('_')[0]

          # Timestamps are big-endian and therefore comparable this way.
          if report_time > self.start_time:
            with open(os.path.join(crash_reports_dir, crash_report)) as f:
              self.summary['logs']['crash report (%s)' % report_time] = (
                f.read().splitlines())

  def GetLaunchCommand(self, test_filter=None, blacklist=False):
    """Returns the iossim invocation which is used to run the test.

    Args:
      test_filter: A list of tests to filter by, or None to mean all.
      blacklist: Whether to blacklist the elements of test_filter or not. Only
        works when test_filter is not None.

    Returns:
      A list whose elements are the args representing the command.
    """
    cmd = [
      self.iossim_path,
      '-d', self.platform,
      '-s', self.version,
      '-t', self.timeout,
      '-u', self.homedir,
    ]
    args = []

    if test_filter is not None:
      kif_filter = self.GetKIFTestFilter(test_filter, blacklist)
      gtest_filter = self.GetGTestFilter(test_filter, blacklist)

      cmd.extend([
       '-e', 'GKIF_SCENARIO_FILTER=%s' % kif_filter,
      ])
      args.append('--gtest_filter=%s' % gtest_filter)

    cmd.append(self.app_path)
    cmd.extend(self.test_args)
    cmd.extend(args)
    return cmd

  @TestRunner.RequireTearDown
  def Launch(self, *args, **kwargs):
    """Launches the test."""
    self.SetUp()

    result = self._Run(self.GetLaunchCommand(), *args, **kwargs)

    if result.crashed and not result.crashed_test:
      # If the app crashed, but there is no specific test which crashed,
      # then the app must have failed to even start. Try one more time.
      self.Print(
        '%s appears to have crashed on startup. Retrying...' % self.app_name,
        blank_lines=2,
        time_to_sleep=5,
      )

      # Use a new home directory to launch a fresh simulator.
      self.KillSimulators()
      self.CreateNewHomeDirectory()

      result = self._Run(self.GetLaunchCommand(), *args, **kwargs)

    return self.RunAllTests(result, *args, **kwargs)
