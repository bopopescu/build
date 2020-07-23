# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for buildbot.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into gcl.
"""

import contextlib
import sys


@contextlib.contextmanager
def pythonpath(path):
  orig = sys.path
  try:
    sys.path = path
    yield
  finally:
    sys.path = orig


def CommonChecks(input_api, output_api):
  def join(*args):
    return input_api.os_path.join(input_api.PresubmitLocalPath(), *args)

  black_list = list(input_api.DEFAULT_BLACK_LIST) + [
      r'.*subordinate/.*/build.*/.*',
      r'.*subordinate/.*/isolate.*/.*',
      r'.*depot_tools/.*',
      r'.*goma/.*',
      r'.*scripts/tools/buildbot_tool_templates/.*',
      r'.*scripts/release/.*',
      r'.*scripts/subordinate/recipe_modules/.*',
      r'.*scripts/subordinate/.recipe_deps/.*',
      r'.*scripts/gsd_generate_index/.*',
      r'.*mains/.*/templates/.*\.html$',
      r'.*mains/.*/templates/.*\.css$',
      r'.*mains/.*/public_html/.*\.html$',
      r'.*mains/.*/public_html/.*\.css$',
      # These gitpoller directories are working directories for
      # main.client.drmemory and main.client.dynamorio and do not contain
      # checked-in code.
      r'.*mains/.*/gitpoller/.*',
  ]
  tests = []

  infra_path = input_api.subprocess.check_output(
      ['python', 'scripts/common/env.py', 'print']).split()

  test_sys_path = infra_path + [
      # Initially, a separate run was done for unit tests but now that
      # pylint is fetched in memory with setuptools, it seems it caches
      # sys.path so modifications to sys.path aren't kept.
      join('scripts', 'main', 'unittests'),
      join('scripts', 'main', 'buildbucket', 'unittests'),
      join('scripts', 'subordinate', 'unittests'),
      join('scripts', 'tools', 'deps2git'),
      join('tests'),
  ] + sys.path
  with pythonpath(test_sys_path):
    disabled_warnings = [
      'C0301',  # Line too long (NN/80)
      'C0321',  # More than one statement on a single line
      'W0613',  # Unused argument
    ]
    tests.extend(input_api.canned_checks.GetPylint(
        input_api,
        output_api,
        black_list=black_list,
        disabled_warnings=disabled_warnings))

  # Run our 'test_env.py' script to generate any required binaries before
  # executing the tests in parallel. Otherwise, individual tests may attempt to
  # generate the binaries at the same time, causing race conflicts.
  input_api.subprocess.check_output(
      ['python', 'scripts/subordinate/unittests/test_env.py'])

  whitelist = [r'.+_test\.py$']
  blacklist = [r'bot_update_test.py$', r'mains_test.py$']
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api, output_api, 'tests', whitelist=whitelist,
      blacklist=blacklist))
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api,
      output_api,
      input_api.os_path.join('scripts', 'main', 'unittests'),
      whitelist))
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api,
      output_api,
      input_api.os_path.join('scripts', 'subordinate', 'unittests'),
      whitelist))
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api,
      output_api,
      input_api.os_path.join('scripts', 'common', 'unittests'),
      whitelist))
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api,
      output_api,
      input_api.os_path.join('scripts', 'tools', 'unittests'),
      whitelist))
  tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
      input_api,
      output_api,
      input_api.os_path.join('scripts', 'tools', 'blink_roller'),
      whitelist))

  recipe_modules_tests = input_api.glob(
      join('scripts', 'subordinate', 'recipe_modules', '*', 'tests'))
  for path in recipe_modules_tests:
    tests.extend(input_api.canned_checks.GetUnitTestsInDirectory(
        input_api,
        output_api,
        path,
        whitelist))

  with pythonpath(infra_path + sys.path):
    import common.main_cfg_utils  # pylint: disable=F0401
    # Fetch recipe dependencies once in serial so that we don't hit a race
    # condition where multiple tests are trying to fetch at once.
    output = input_api.RunTests([input_api.Command(
        name='recipes fetch',
        cmd=[input_api.python_executable,
             input_api.os_path.join('scripts', 'subordinate', 'recipes.py'), 'fetch'],
        kwargs={},
        message=output_api.PresubmitError,
    )])
    # Run the tests.
    with common.main_cfg_utils.TemporaryMainPasswords():
      output.extend(input_api.RunTests(tests))

    output.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api, excluded_paths=black_list))
    return output


def ConditionalChecks(input_api, output_api):
  """Pre-commit tests only to be run if specific files have changed.

  Typically, this is used to avoid running lengthy tests when possible.
  """
  tests_to_run = []
  conditional_tests = {
      'scripts/subordinate/bot_update.py': ['tests/bot_update_test.py'],
  }
  affected_files = set([
      f.LocalPath() for f in input_api.change.AffectedFiles()])
  for key, val in conditional_tests.iteritems():
    if key in affected_files:
      tests_to_run.extend(val)
  return input_api.RunTests(input_api.canned_checks.GetUnitTests(
      input_api, output_api, tests_to_run))

def CommitChecks(input_api, output_api):
  """Tests that are only run on commit."""
  tests_to_run = ['tests/mains_test.py']
  return input_api.RunTests(input_api.canned_checks.GetUnitTests(
      input_api, output_api, tests_to_run))

def BuildInternalCheck(output, input_api, output_api):
  if output:
    b_i = input_api.os_path.join(input_api.PresubmitLocalPath(), '..',
                                 'build_internal')
    if input_api.os_path.exists(b_i):
      return [output_api.PresubmitNotifyResult(
          'You have a build_internal checkout. '
          'Updating it may resolve some issues.')]
  return []


def CheckChangeOnUpload(input_api, output_api):
  return [] # Try-jobs/commit-queue do a better job of testing, faster.


def CheckChangeOnCommit(input_api, output_api):
  output = CommonChecks(input_api, output_api)
  output.extend(ConditionalChecks(input_api, output_api))
  output.extend(CommitChecks(input_api, output_api))
  output.extend(BuildInternalCheck(output, input_api, output_api))
  return output
