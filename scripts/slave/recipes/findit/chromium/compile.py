# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine.config import List
from recipe_engine.config import Single
from recipe_engine.recipe_api import Property


DEPS = [
    'chromium',
    'chromium_tests',
    'findit',
    'depot_tools/gclient',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
]


PROPERTIES = {
    'target_mainname': Property(
        kind=str, help='The target main to match compile config to.'),
    'target_buildername': Property(
        kind=str, help='The target builder to match compile config to.'),
    'good_revision': Property(
        kind=str, help='The last known good chromium revision.'),
    'bad_revision': Property(
        kind=str, help='The first known bad chromium revision.'),
    'compile_targets': Property(
        kind=List(basestring), default=None,
        help='The failed compile targets, eg: browser_tests, '
             'obj/path/to/source.o, gen/path/to/generated.cc, etc.'),
    'use_analyze': Property(
        kind=Single(bool, empty_val=False, required=False), default=True,
        help='Use analyze to filter out affected targets.'),
}


class CompileResult(object):
  SKIPPED = 'skipped'  # No compile is needed.
  PASSED = 'passed'  # Compile passed.
  FAILED = 'failed'  # Compile failed.


def _run_compile_at_revision(api, target_mainname, target_buildername,
                             revision, compile_targets, use_analyze):
  with api.step.nest('test %s' % str(revision)):
    # Checkout code at the given revision to recompile.
    bot_config = api.chromium_tests.create_bot_config_object(
        target_mainname, target_buildername)
    bot_update_step, bot_db = api.chromium_tests.prepare_checkout(
        bot_config, root_solution_revision=revision)

    compile_targets = sorted(set(compile_targets or []))
    if not compile_targets:
      # If compile targets are not specified, retrieve them from the build spec.
      _, tests_including_triggered = api.chromium_tests.get_tests(
          bot_config, bot_db)
      compile_targets = api.chromium_tests.get_compile_targets(
          bot_config, bot_db, tests_including_triggered)

      # Use dependency "analyze" to filter out those that are not impacted by
      # the given revision. This is to reduce the number of targets to be
      # compiled.
      if use_analyze:
        changed_files = api.findit.files_changed_by_revision(revision)

        _, compile_targets = api.chromium_tests.analyze(
            changed_files,
            test_targets=[],
            additional_compile_targets=compile_targets,
            config_file_name='trybot_analyze_config.json',
            mb_mainname=target_mainname,
            mb_buildername=target_buildername,
            additional_names=None)
    else:
      # Use ninja to filter out none-existing targets.
      compile_targets = api.findit.existing_targets(
          compile_targets, target_mainname, target_buildername)

    if not compile_targets:
      # No compile target exists, or is impacted by the given revision.
      return CompileResult.SKIPPED

    try:
      api.chromium_tests.compile_specific_targets(
          bot_config,
          bot_update_step,
          bot_db,
          compile_targets,
          tests_including_triggered=[],
          mb_mainname=target_mainname,
          mb_buildername=target_buildername,
          override_bot_type='builder_tester')
      return CompileResult.PASSED
    except api.step.InfraFailure:
      raise
    except api.step.StepFailure:
      return CompileResult.FAILED


def RunSteps(api, target_mainname, target_buildername,
             good_revision, bad_revision,
             compile_targets, use_analyze):
  bot_config = api.chromium_tests.create_bot_config_object(
      target_mainname, target_buildername)
  api.chromium_tests.configure_build(
      bot_config, override_bot_type='builder_tester')

  # Sync to bad revision, and retrieve revisions in the regression range.
  api.chromium_tests.prepare_checkout(
      bot_config,
      root_solution_revision=bad_revision)
  revisions_to_check = api.findit.revisions_between(good_revision, bad_revision)

  compile_results = {}
  try_job_metadata = {
      'regression_range_size': len(revisions_to_check)
  }
  report = {
      'result': compile_results,
      'metadata': try_job_metadata,
  }

  try:
    for current_revision in revisions_to_check:
      last_revision = None
      compile_result = _run_compile_at_revision(
          api, target_mainname, target_buildername,
          current_revision, compile_targets, use_analyze)

      compile_results[current_revision] = compile_result
      last_revision = current_revision
      if compile_result == CompileResult.FAILED:
        break  # Found the culprit, no need to check later revisions.
  finally:
    # Report the result.
    step_result = api.python.succeeding_step(
        'report', [json.dumps(report, indent=2)], as_log='report')

    if (last_revision and
        compile_results.get(last_revision) == CompileResult.FAILED):
      step_result.presentation.step_text = '<br/>Culprit: %s' % last_revision

    # Set the report as a build property too, so that it will be reported back
    # to Buildbucket and Findit will pull from there instead of buildbot main.
    step_result.presentation.properties['report'] = report

  return report


def GenTests(api):
  def props(compile_targets=None, use_analyze=False):
    properties = {
        'mainname': 'tryserver.chromium.linux',
        'buildername': 'linux_variable',
        'subordinatename': 'build1-a1',
        'buildnumber': '1',
        'target_mainname': 'chromium.linux',
        'target_buildername': 'Linux Builder',
        'good_revision': 'r0',
        'bad_revision': 'r1',
        'use_analyze': use_analyze,
    }
    if compile_targets:
      properties['compile_targets'] = compile_targets
    return api.properties(**properties) + api.platform.name('linux')

  yield (
      api.test('compile_specified_targets') +
      props(compile_targets=['target_name']) +
      api.override_step_data('test r1.check_targets',
                             api.json.output({
                                 'found': ['target_name'],
                                 'not_found': [],
                             }))
  )

  yield (
      api.test('compile_none_existing_targets') +
      props(compile_targets=['gen/a/b/source.cc']) +
      api.override_step_data('test r1.check_targets',
                             api.json.output({
                                 'found': [],
                                 'not_found': ['gen/a/b/source.cc'],
                             }))
  )


  yield (
      api.test('compile_default_targets') +
      props() +
      api.override_step_data('test r1.read test spec',
                             api.json.output({
                                 'Linux Builder': {
                                     'additional_compile_targets': [
                                         'base_unittests',
                                     ],
                                 }
                             }))
  )

  yield (
      api.test('compile_succeeded') +
      props() +
      api.override_step_data('test r1.compile', retcode=0)
  )

  yield (
      api.test('compile_failed') +
      props() +
      api.override_step_data('test r1.compile', retcode=1)
  )

  yield (
      api.test('failed_compile_upon_infra_failure_goma_setup_failure') +
      props(compile_targets=['target_name']) +
      api.override_step_data('test r1.check_targets',
                             api.json.output({
                                 'found': ['target_name'],
                                 'not_found': [],
                             })) +
      api.override_step_data(
          'test r1.compile',
          api.json.output({
              'notice': [
                  {
                      "compile_error": "COMPILER_PROXY_UNREACHABLE",
                  },
              ],
          }),
          retcode=1)
  )

  yield (
      api.test('failed_compile_upon_infra_failure_goma_ping_failure') +
      props(compile_targets=['target_name']) +
      api.override_step_data('test r1.check_targets',
                             api.json.output({
                                 'found': ['target_name'],
                                 'not_found': [],
                             })) +
      api.override_step_data(
          'test r1.compile',
          api.json.output({
              'notice': [
                  {
                      'infra_status': {
                          'ping_status_code': 408,
                      },
                  },
              ],
          }),
          retcode=1)
  )

  yield (
      api.test('failed_compile_upon_infra_failure_goma_build_error') +
      props(compile_targets=['target_name']) +
      api.override_step_data('test r1.check_targets',
                             api.json.output({
                                 'found': ['target_name'],
                                 'not_found': [],
                             })) +
      api.override_step_data(
          'test r1.compile',
          api.json.output({
              'notice': [
                  {
                      'infra_status': {
                          'ping_status_code': 200,
                          'num_user_error': 1,
                      },
                  },
              ],
          }),
          retcode=1)
  )

  yield (
      api.test('compile_skipped') +
      props(use_analyze=True) +
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
      api.test('compile_affected_targets_only') +
      props(use_analyze=True) +
      api.override_step_data('test r1.read test spec',
                             api.json.output({
                                 'Linux Builder': {
                                     'additional_compile_targets': [
                                         'a', 'a_run',
                                         'b', 'b_run',
                                     ],
                                 }
                             })) +
      api.override_step_data(
          'test r1.analyze',
          api.json.output({
              'status': 'Found dependency',
              'compile_targets': ['a', 'a_run'],
              'test_targets': ['a', 'a_run'],
          })
      )
  )
