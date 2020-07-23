# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine.config import Dict
from recipe_engine.config import Single
from recipe_engine.recipe_api import Property


DEPS = [
    'adb',
    'depot_tools/bot_update',
    'chromium',
    'chromium_tests',
    'commit_position',
    'findit',
    'depot_tools/gclient',
    'isolate',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/raw_io',
    'recipe_engine/step',
    'swarming',
    'test_results',
    'test_utils',
]


PROPERTIES = {
    'target_mainname': Property(
        kind=str, help='The target main to match compile config to.'),
    'target_testername': Property(
        kind=str,
        help='The target tester to match test config to. If the tests are run '
             'on a builder, just treat the builder as a tester.'),
    'good_revision': Property(
        kind=str, help='The last known good revision.'),
    'bad_revision': Property(
        kind=str, help='The first known good revision.'),
    'tests': Property(
        kind=Dict(value_type=list),
        help='The failed tests, the test name should be full name, e.g.: {'
             '  "browser_tests": ['
             '    "suite.test1", "suite.test2"'
             '  ]'
             '}'),
    'use_analyze': Property(
        kind=Single(bool, empty_val=False, required=False), default=True,
        help='Use analyze to skip commits that do not affect tests.'),
}


class TestResult(object):
  SKIPPED = 'skipped'  # A commit doesn't impact the test.
  PASSED = 'passed'  # The compile or test passed.
  FAILED = 'failed'  # The compile or test failed.


def _compile_and_test_at_revision(api, target_mainname, target_buildername,
                                  target_testername, revision, requested_tests,
                                  use_analyze):
  results = {}
  with api.step.nest('test %s' % str(revision)):
    # Checkout code at the given revision to recompile.
    bot_config = api.chromium_tests.create_bot_config_object(
        target_mainname, target_buildername)
    bot_update_step, bot_db = api.chromium_tests.prepare_checkout(
        bot_config, root_solution_revision=revision)

    # Figure out which test steps to run.
    _, all_tests = api.chromium_tests.get_tests(bot_config, bot_db)
    requested_tests_to_run = [
        test for test in all_tests if test.name in requested_tests]

    # Figure out the test targets to be compiled.
    requested_test_targets = []
    for test in requested_tests_to_run:
      requested_test_targets.extend(test.compile_targets(api))
    requested_test_targets = sorted(set(requested_test_targets))

    actual_tests_to_run = requested_tests_to_run
    actual_compile_targets = requested_test_targets
    # Use dependency "analyze" to reduce tests to be run.
    if use_analyze:
      changed_files = api.findit.files_changed_by_revision(revision)

      affected_test_targets, actual_compile_targets = (
          api.chromium_tests.analyze(
              changed_files,
              test_targets=requested_test_targets,
              additional_compile_targets=[],
              config_file_name='trybot_analyze_config.json',
              mb_mainname=target_mainname,
              mb_buildername=target_buildername,
              additional_names=None))

      actual_tests_to_run = []
      for test in requested_tests_to_run:
        targets = test.compile_targets(api)
        if not targets:
          # No compile is needed for the test. Eg: checkperms.
          actual_tests_to_run.append(test)
          continue

        # Check if the test is affected by the given revision.
        for target in targets:
          if target in affected_test_targets:
            actual_tests_to_run.append(test)
            break

    if actual_compile_targets:
      api.chromium_tests.compile_specific_targets(
          bot_config,
          bot_update_step,
          bot_db,
          actual_compile_targets,
          tests_including_triggered=actual_tests_to_run,
          mb_mainname=target_mainname,
          mb_buildername=target_buildername,
          override_bot_type='builder_tester')

    # Run the tests.
    with api.chromium_tests.wrap_chromium_tests(
        bot_config, actual_tests_to_run):
      failed_tests = api.test_utils.run_tests(
          api, actual_tests_to_run,
          suffix=revision, test_filters=requested_tests)

    # Process failed tests.
    for failed_test in failed_tests:
      valid = failed_test.has_valid_results(api, suffix=revision)
      results[failed_test.name] = {
          'status': TestResult.FAILED,
          'valid': valid,
      }
      if valid:
        results[failed_test.name]['failures'] = list(
            failed_test.failures(api, suffix=revision))

    # Process passed tests.
    for test in actual_tests_to_run:
      if test not in failed_tests:
        results[test.name] = {
            'status': TestResult.PASSED,
            'valid': True,
        }

    # Process skipped tests in two scenarios:
    # 1. Skipped by "analyze": tests are not affected by the given revision.
    # 2. Skipped because the requested tests don't exist at the given revision.
    for test_name in requested_tests.keys():
      if test_name not in results:
        results[test_name] = {
            'status': TestResult.SKIPPED,
            'valid': True,
        }

    return results


def RunSteps(api, target_mainname, target_testername,
             good_revision, bad_revision, tests, use_analyze):
  assert tests, 'No failed tests were specified.'

  # Figure out which builder configuration we should match for compile config.
  # Sometimes, the builder itself runs the tests and there is no tester. In
  # such cases, just treat the builder as a "tester". Thus, we default to
  # the target tester.
  tester_config = api.chromium_tests.builders.get(
      target_mainname).get('builders', {}).get(target_testername)
  target_buildername = (tester_config.get('parent_buildername') or
                        target_testername)

  # Configure to match the compile config on the builder.
  bot_config = api.chromium_tests.create_bot_config_object(
      target_mainname, target_buildername)
  api.chromium_tests.configure_build(
      bot_config, override_bot_type='builder_tester')

  # Configure to match the test config on the tester, as builders don't have the
  # settings for swarming tests.
  if target_buildername != target_testername:
    for key, value in tester_config.get('swarming_dimensions', {}).iteritems():
      api.swarming.set_default_dimension(key, value)
  # TODO(stgao): Fix the issue that precommit=False adds the tag 'purpose:CI'.
  api.chromium_tests.configure_swarming('chromium', precommit=False)

  # Sync to bad revision, and retrieve revisions in the regression range.
  api.chromium_tests.prepare_checkout(
      bot_config,
      root_solution_revision=bad_revision)
  revisions_to_check = api.findit.revisions_between(good_revision, bad_revision)

  test_results = {}
  try_job_metadata = {
      'regression_range_size': len(revisions_to_check)
  }
  report = {
      'result': test_results,
      'metadata': try_job_metadata
  }

  try:
    # We compile & run tests from the first revision to the last revision in the
    # regression range serially instead of a typical bisecting, because jumping
    # between new and old revisions might affect Goma capacity and build cycle
    # times. Thus we plan to go with this simple serial approach first so that
    # compile would be fast due to incremental compile.
    # If this won't work out, we will figure out a better solution for speed of
    # both compile and test.
    for current_revision in revisions_to_check:
      test_results[current_revision] = _compile_and_test_at_revision(
          api, target_mainname, target_buildername, target_testername,
          current_revision, tests, use_analyze)
      # TODO(http://crbug.com/566975): check whether culprits for all failed
      # tests are found and stop running tests at later revisions if so.
  finally:
    # Give the full report including test results and metadata.
    step_result = api.python.succeeding_step(
        'report', [json.dumps(report, indent=2)], as_log='report')

    # Set the report as a build property too, so that it will be reported back
    # to Buildbucket and Findit will pull from there instead of buildbot main.
    step_result.presentation.properties['report'] = report

  return report


def GenTests(api):
  def props(tests, platform_name, tester_name, use_analyze=False):
    properties = {
        'mainname': 'tryserver.chromium.%s' % platform_name,
        'buildername': '%s_chromium_variable' % platform_name,
        'subordinatename': 'build1-a1',
        'buildnumber': 1,
        'target_mainname': 'chromium.%s' % platform_name,
        'target_testername': tester_name,
        'good_revision': 'r0',
        'bad_revision': 'r1',
        'tests': tests,
        'use_analyze': use_analyze,
    }
    return api.properties(**properties) + api.platform.name(platform_name)

  def simulated_gtest_output(failed_test_names=(), passed_test_names=()):
    cur_iteration_data = {}
    for test_name in failed_test_names:
      cur_iteration_data[test_name] = [{
          'elapsed_time_ms': 0,
          'output_snippet': '',
          'status': 'FAILURE',
      }]
    for test_name in passed_test_names:
      cur_iteration_data[test_name] = [{
          'elapsed_time_ms': 0,
          'output_snippet': '',
          'status': 'SUCCESS',
      }]

    canned_jsonish = {
        'per_iteration_data': [cur_iteration_data]
    }

    return api.test_utils.raw_gtest_output(
        canned_jsonish, 1 if failed_test_names else 0)

  yield (
      api.test('nonexistent_test_step_skipped') +
      props({'newly_added_tests': ['Test.One', 'Test.Two', 'Test.Three']},
            'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      }))
  )

  yield (
      api.test('unaffected_test_skipped_by_analyze') +
      props({'affected_tests': ['Test.One'], 'unaffected_tests': ['Test.Two']},
            'win', 'Win7 Tests (1)', use_analyze=True) +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                    'test': 'affected_tests',
                    'swarming': {'can_use_on_swarming_builders': True},
                  },
                  {
                    'test': 'unaffected_tests',
                    'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.analyze',
          api.json.output({
              'status': 'Found dependency',
              'compile_targets': ['affected_tests', 'affected_tests_run'],
              'test_targets': ['affected_tests', 'affected_tests_run'],
          })
      ) +
      api.override_step_data(
          'test r1.affected_tests (r1) on Windows-7-SP1',
          simulated_gtest_output(passed_test_names=['Test.One'])
      )
  )

  yield (
      api.test('test_without_targets_not_skipped') +
      props({'unaffected_tests': ['Test.One'], 'checkperms': []},
            'win', 'Win7 Tests (1)', use_analyze=True) +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                    'test': 'unaffected_tests',
                    'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
              'scripts': [
                  {
                      'name': 'checkperms',
                      'script': 'checkperms.py'
                  },
              ]
          },
      })) +
      api.override_step_data(
          'test r1.analyze',
          api.json.output({
              'status': 'No dependencies',
              'compile_targets': [],
              'test_targets': [],
          })
      )
  )

  yield (
      api.test('all_test_failed') +
      props({'gl_tests': ['Test.One', 'Test.Two', 'Test.Three']},
            'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.gl_tests (r1) on Windows-7-SP1',
          simulated_gtest_output(
              failed_test_names=['Test.One', 'Test.Two', 'Test.Three'])
      )
  )

  yield (
      api.test('all_test_passed') +
      props({'gl_tests': ['Test.One', 'Test.Two', 'Test.Three']},
            'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.gl_tests (r1) on Windows-7-SP1',
          simulated_gtest_output(
              passed_test_names=['Test.One', 'Test.Two', 'Test.Three'])
      )
  )

  yield (
      api.test('only_one_test_passed') +
      props({'gl_tests': ['Test.One', 'Test.Two', 'Test.Three']},
            'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.gl_tests (r1) on Windows-7-SP1',
          simulated_gtest_output(
              failed_test_names=['Test.One', 'Test.Two'],
              passed_test_names=['Test.Three'])
      )
  )

  yield (
      api.test('compile_skipped') +
      props({'checkperms': []}, 'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'scripts': [
                  {
                      'name': 'checkperms',
                      'script': 'checkperms.py'
                  },
              ]
          },
      }))
  )

  yield (
      api.test('none_swarming_tests') +
      props({'gl_tests': ['Test.One', 'Test.Two', 'Test.Three']},
            'win', 'Win7 Tests (1)') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Win7 Tests (1)': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': False},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.gl_tests (r1)',
          simulated_gtest_output(
              failed_test_names=['Test.One', 'Test.Two'],
              passed_test_names=['Test.Three'])
      )
  )

  yield (
      api.test('swarming_tests') +
      props({'gl_tests': ['Test.One']}, 'mac', 'Mac10.9 Tests') +
      api.override_step_data('test r1.read test spec', api.json.output({
          'Mac10.9 Tests': {
              'gtest_tests': [
                  {
                      'test': 'gl_tests',
                      'swarming': {'can_use_on_swarming_builders': True},
                  },
              ],
          },
      })) +
      api.override_step_data(
          'test r1.gl_tests (r1) on Mac-10.9',
          simulated_gtest_output(passed_test_names=['Test.One'])
      )
  )
