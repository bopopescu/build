# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from recipe_engine.types import freeze

DEPS = [
  'amp',
  'depot_tools/bot_update',
  'chromium',
  'chromium_android',
  'chromium_tests',
  'commit_position',
  'file',
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
  'depot_tools/tryserver',
]


# TODO(phajdan.jr): Remove special case for layout tests.
# This could be done by moving layout tests to main waterfall.
CHROMIUM_BLINK_TESTS_BUILDERS = freeze([
  'linux_chromium_rel_ng',
  'mac_chromium_rel_ng',
  'win_chromium_rel_ng',
])


CHROMIUM_BLINK_TESTS_PATHS = freeze([
  # Service worker code is primarily tested in Blink layout tests.
  'content/browser/bluetooth',
  'content/browser/service_worker',
  'content/child/service_worker',
  'content/common/bluetooth',
  'content/renderer/bluetooth',
  'content/renderer/service_worker',
  'content/shell/browser/layout_test',
  'device/bluetooth',
  'device/usb/public/interfaces',
  'media',
  'third_party/WebKit',
  'third_party/harfbuzz-ng',
  'third_party/iccjpeg',
  'third_party/libjpeg',
  'third_party/libjpeg_turbo',
  'third_party/libpng',
  'third_party/libwebp',
  'third_party/qcms',
  'third_party/yasm',
  'third_party/zlib',
  'v8',
])


def tests_in_compile_targets(api, compile_targets, tests):
  """Returns the tests in |tests| that have at least one of their compile
  targets in |compile_targets|."""
  result = []
  for test in tests:
    test_compile_targets = test.compile_targets(api)

    # Always return tests that don't require compile. Otherwise we'd never
    # run them.
    if ((set(compile_targets).intersection(set(test_compile_targets))) or
        not test_compile_targets):
      result.append(test)

  return result


def all_compile_targets(api, tests):
  """Returns the compile_targets for all the Tests in |tests|."""
  return sorted(set(x
                    for test in tests
                    for x in test.compile_targets(api)))


def is_source_file(api, filepath):
  """Returns true iff the file is a source file."""
  _, ext = api.path.splitext(filepath)
  return ext in ['.c', '.cc', '.cpp', '.h', '.java', '.mm']

def _RunStepsInternal(api):
  def _get_bot_config(mastername, buildername):
    master_dict = api.chromium_tests.trybots.get(mastername, {})
    return master_dict.get('builders', {}).get(buildername)

  mastername = api.properties.get('mastername')
  buildername = api.properties.get('buildername')
  bot_config = _get_bot_config(mastername, buildername)

  bot_config_object = api.chromium_tests.create_generalized_bot_config_object(
      bot_config['bot_ids'])
  api.chromium_tests.set_precommit_mode()
  api.chromium_tests.configure_build(
      bot_config_object, override_bot_type='builder_tester')

  api.chromium_tests.configure_swarming('chromium', precommit=True)

  api.chromium.apply_config('trybot_flavor')

  if api.properties.get('patch_project') == 'blink':  # pragma: no cover
    raise Exception('CLs which use blink project are not supported. '
                    'Please re-create the CL using fresh checkout after '
                    'the blink merge.')

  bot_update_step, bot_db = api.chromium_tests.prepare_checkout(
      bot_config_object)

  tests, tests_including_triggered = api.chromium_tests.get_tests(
      bot_config_object, bot_db)
  def add_tests(additional_tests):
    tests.extend(additional_tests)
    tests_including_triggered.extend(additional_tests)

  affected_files = api.tryserver.get_files_affected_by_patch()

  affects_blink_paths = False
  for path in CHROMIUM_BLINK_TESTS_PATHS:
    if any([f.startswith(path) for f in affected_files]):
      affects_blink_paths = True

  affects_blink = any([f.startswith('third_party/WebKit')
                       for f in affected_files])

  if affects_blink:
    subproject_tag = 'blink'
  elif affects_blink_paths:
    subproject_tag = 'blink-paths'
  else:
    subproject_tag = 'chromium'
  api.tryserver.set_subproject_tag(subproject_tag)

  # TODO(phajdan.jr): Remove special case for layout tests.
  add_blink_tests = (affects_blink_paths and
                     buildername in CHROMIUM_BLINK_TESTS_BUILDERS)

  # Add blink tests that work well with "analyze" here. The tricky ones
  # that bypass it (like the layout tests) are added later.
  if add_blink_tests:
    add_tests([
        api.chromium_tests.steps.GTestTest('blink_heap_unittests'),
        api.chromium_tests.steps.GTestTest('blink_platform_unittests'),
        api.chromium_tests.steps.GTestTest('webkit_unit_tests'),
        api.chromium_tests.steps.GTestTest('wtf_unittests'),
    ])

  compile_targets = api.chromium_tests.get_compile_targets(
      bot_config_object,
      bot_db,
      tests_including_triggered)

  test_targets = sorted(set(
      all_compile_targets(api, tests + tests_including_triggered)))
  additional_compile_targets = sorted(set(compile_targets) -
                                      set(test_targets))
  test_targets, compile_targets = \
      api.chromium_tests.analyze(affected_files,
                                 test_targets,
                                 additional_compile_targets,
                                 'trybot_analyze_config.json')

  if bot_config.get('analyze_mode') == 'compile':
    tests = []
    tests_including_triggered = []

  # Blink tests have to bypass "analyze", see below.
  if compile_targets or add_blink_tests:
    tests = tests_in_compile_targets(api, test_targets, tests)
    tests_including_triggered = tests_in_compile_targets(
        api, test_targets, tests_including_triggered)

    # Blink tests are tricky at this moment. We'd like to use "analyze" for
    # everything else. However, there are blink changes that only add or modify
    # layout test files (html etc). This is not recognized by "analyze" as
    # compile dependency. However, the blink tests should still be executed.
    if add_blink_tests:
      blink_tests = [
          api.chromium_tests.steps.ScriptTest(
              'webkit_lint', 'webkit_lint.py', collections.defaultdict(list)),
          api.chromium_tests.steps.ScriptTest(
              'webkit_python_tests', 'webkit_python_tests.py',
              collections.defaultdict(list)),
          api.chromium_tests.steps.BlinkTest(),
      ]
      add_tests(blink_tests)
      for test in blink_tests:
        compile_targets.extend(test.compile_targets(api))
      compile_targets = sorted(set(compile_targets))

    api.chromium_tests.compile_specific_targets(
        bot_config_object,
        bot_update_step,
        bot_db,
        compile_targets,
        tests_including_triggered,
        override_bot_type='builder_tester')
  else:
    # Even though the patch doesn't require a compile on this platform,
    # we'd still like to run tests not depending on
    # compiled targets (that's obviously not covered by the
    # 'analyze' step) if any source files change.
    if any([is_source_file(api, f) for f in affected_files]):
      tests = [t for t in tests if not t.compile_targets(api)]
    else:
      tests = []

  return bot_config_object, bot_update_step, affected_files, tests


def RunSteps(api):
  # build/tests/masters_recipes_tests.py needs to manipulate the BUILDERS
  # dict, so we provide an API to dump it here.
  if api.properties.get('dump_builders'):  # pragma: no cover
    api.file.copy('Dump BUILDERS dict',
        api.json.input(api.chromium_tests.trybots),
        api.properties['dump_builders'])
    return

  with api.tryserver.set_failure_hash():
    try:
      bot_config_object, bot_update_step, affected_files, tests = \
          _RunStepsInternal(api)
    finally:
      api.python.succeeding_step('mark: before_tests', '')

    if tests:
      api.chromium_tests.run_tests_on_tryserver(
          bot_config_object, api, tests, bot_update_step, affected_files)


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  canned_test = api.test_utils.canned_gtest_output

  def props(config='Release', mastername='tryserver.chromium.linux',
            buildername='linux_chromium_rel_ng', extra_swarmed_tests=None,
            **kwargs):
    kwargs.setdefault('revision', None)
    swarm_hashes = {}
    if extra_swarmed_tests:
      for test in extra_swarmed_tests:
        swarm_hashes[test] = '[dummy hash for %s]' % test
    return api.properties.tryserver(
      build_config=config,
      mastername=mastername,
      buildername=buildername,
      swarm_hashes=swarm_hashes,
      **kwargs
    )

  def suppress_analyze(more_exclusions=None):
    """Overrides analyze step data so that all targets get compiled."""
    return api.override_step_data(
        'read filter exclusion spec',
        api.json.output({
            'base': {
                'exclusions': ['f.*'] + (more_exclusions or []),
            },
            'chromium': {
                'exclusions': [],
            },
        })
    )

  # While not strictly required for coverage, record expectations for each
  # of the configs so we can see when and how they change.
  for mastername, master_config in api.chromium_tests.trybots.iteritems():
    for buildername, bot_config in master_config['builders'].iteritems():
      test_name = 'full_%s_%s' % (_sanitize_nonalpha(mastername),
                                  _sanitize_nonalpha(buildername))
      yield (
        api.test(test_name) +
        api.chromium_tests.platform(bot_config['bot_ids']) +
        suppress_analyze() +
        props(mastername=mastername, buildername=buildername)
      )

  yield (
    api.test('chromeos_analyze') +
    api.platform.name('linux') +
    props(mastername='tryserver.chromium.linux',
          buildername='chromeos_amd64-generic_chromium_compile_only_ng')
  )

  # Additional tests for blink trybots.
  blink_trybots = api.chromium_tests.trybots['tryserver.blink']['builders']
  for buildername, bot_config in blink_trybots.iteritems():
    if bot_config.get('analyze_mode') == 'compile':
      continue

    for pass_first in (True, False):
      test_name = 'full_%s_%s_%s' % (_sanitize_nonalpha('tryserver.blink'),
                                     _sanitize_nonalpha(buildername),
                                     'pass' if pass_first else 'fail')
      test = (api.test(test_name) +
              suppress_analyze() +
              props(mastername='tryserver.blink',
                    buildername=buildername) +
              api.chromium_tests.platform(bot_config['bot_ids']) +
              api.override_step_data('webkit_tests (with patch)',
                  api.test_utils.canned_test_output(passing=pass_first)))
      if not pass_first:
        test += api.override_step_data('webkit_tests (without patch)',
            api.test_utils.canned_test_output(passing=False, minimal=True))
      yield test

  # Regression test for http://crbug.com/453471#c16
  yield (
    api.test('clobber_analyze') +
    props(buildername='linux_chromium_clobber_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data(
      'analyze',
      api.json.output({
          'status': 'Found dependency',
          'test_targets': [],
          'compile_targets': ['base_unittests', 'net_unittests']
      }))
  )

  # Do not fail the build if process_dumps fails.
  # http://crbug.com/520660
  yield (
    api.test('process_dumps_failure') +
    props(mastername='tryserver.chromium.win',
          buildername='win_chromium_rel_ng') +
    api.platform.name('win') +
    suppress_analyze() +
    api.override_step_data('process_dumps', retcode=1)
  )

  yield (
    api.test('invalid_results') +
    props() +
    api.platform.name('linux') +
    # TODO(kbr): disambiguate multiple "read test spec" steps better
    # for trybots which mirror multiple waterfall bots.
    api.override_step_data('read test spec (2)', api.json.output({
        'Linux Tests': {
            'gtest_tests': ['base_unittests'],
        },
    })) +
    suppress_analyze() +
    api.override_step_data('base_unittests (with patch)',
                           canned_test(passing=False)) +
    api.override_step_data('base_unittests (without patch)',
                           api.test_utils.raw_gtest_output(None, retcode=1))
  )

  yield (
    api.test('script_test_with_overridden_compile_targets') +
      props() +
      api.platform.name('linux') +
      api.override_step_data('read test spec (2)', api.json.output({
          'Linux Tests': {
              'scripts': [
                  {
                      'name': 'script_test',
                      'script': 'fake_script.py',
                      'override_compile_targets': ['overridden_target']
                  }
              ],
          }}))
  )

  yield (
    api.test('dynamic_isolated_script_test_with_args_on_trybot') +
    props(extra_swarmed_tests=['telemetry_gpu_unittests']) +
    api.platform.name('linux') +
    api.override_step_data('read test spec (2)', api.json.output({
        'Linux Tests': {
            'isolated_scripts': [
                {
                  'isolate_name': 'telemetry_gpu_unittests',
                  'name': 'telemetry_gpu_unittests',
                  'args': ['--correct-common-arg'],
                  'non_precommit_args': [
                    '--SHOULD-NOT-BE-PRESENT-DURING-THE-RUN'
                  ],
                  'precommit_args': [
                    '--these-args-should-be-present',
                    '--test-machine-name=\"${buildername}\"',
                    '--build-revision=\"${got_revision}\"',
                  ],
                  'swarming': {'can_use_on_swarming_builders': True},
                },
            ],
        },
    })) +
    suppress_analyze() +
    api.override_step_data(
        'telemetry_gpu_unittests (with patch) on Ubuntu-12.04',
        api.test_utils.canned_isolated_script_output(
            passing=True, is_win=False, swarming=True))
  )

  yield (
    api.test('swarming_test_with_priority_and_expiration') +
    props(extra_swarmed_tests=['gl_tests']) +
    api.platform.name('linux') +
    api.override_step_data('read test spec (2)', api.json.output({
        'Linux Tests': {
            'gtest_tests': [
                {
                  'test': 'gl_tests',
                  'swarming': {
                    'can_use_on_swarming_builders': True,
                    'priority_adjustment': 'higher',
                    'expiration': 7200,
                  },
                },
            ],
        },
    })) +
    suppress_analyze()
  )

  yield (
    api.test('swarming_trigger_failure') +
    props() +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({
        'Linux Tests': {
            'gtest_tests': [
                {
                  'test': 'base_unittests',
                  'swarming': {'can_use_on_swarming_builders': True},
                },
            ],
        },
    })) +
    suppress_analyze()
  )

  yield (
    api.test('swarming_test_failure') +
    props(extra_swarmed_tests=['gl_tests']) +
    api.platform.name('linux') +
    api.override_step_data('read test spec (2)', api.json.output({
        'Linux Tests': {
            'gtest_tests': [
                {
                  'test': 'gl_tests',
                  'swarming': {'can_use_on_swarming_builders': True},
                },
            ],
        },
    })) +
    suppress_analyze() +
    api.override_step_data('gl_tests (with patch) on Ubuntu-12.04',
                           canned_test(passing=False))
  )

  yield (
    api.test('amp_test_failure') +
    props(buildername='android_amp',
          mastername='tryserver.chromium.android') +
    api.platform.name('linux') +
    suppress_analyze() +
    api.override_step_data('[collect] base_unittests (with patch)',
                           canned_test(passing=False), retcode=1)
  )

  yield (
    api.test('amp_test_local_fallback') +
    props(buildername='android_amp',
          mastername='tryserver.chromium.android') +
    api.platform.name('linux') +
    suppress_analyze() +
    api.override_step_data('[trigger] base_unittests (with patch)',
                           retcode=1)
  )

  yield (
    api.test('amp_test_local_fallback_failure') +
    props(buildername='android_amp',
          mastername='tryserver.chromium.android') +
    api.platform.name('linux') +
    suppress_analyze() +
    api.override_step_data('[trigger] base_unittests (with patch)',
                           retcode=1) +
    api.override_step_data('base_unittests (with patch)',
                           canned_test(passing=False), retcode=1)
  )

  yield (
    api.test('compile_failure_without_patch_deapply_fn') +
    props() +
    api.platform.name('linux') +
    api.override_step_data('read test spec (2)', api.json.output({
        'Linux Tests': {
          'gtest_tests': ['base_unittests'],
        },
      })
    ) +
    suppress_analyze() +
    api.override_step_data('base_unittests (with patch)',
                           canned_test(passing=False)) +
    api.override_step_data('compile (without patch)', retcode=1)
  )

  yield (
    api.test('compile_failure_infra') +
    props() +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({
        'Linux Tests': {
          'gtest_tests': ['base_unittests'],
        },
      })
    ) +
    suppress_analyze() +
    api.override_step_data(
        'compile (with patch)',
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

  for step in ('bot_update', 'gclient runhooks (with patch)'):
    yield (
      api.test(_sanitize_nonalpha(step) + '_failure') +
      props() +
      api.platform.name('linux') +
      api.step_data(step, retcode=1)
    )

  yield (
    api.test('runhooks_failure') +
    props(buildername='win_chromium_rel_ng',
          mastername='tryserver.chromium.win') +
    api.platform.name('win') +
    api.step_data('gclient runhooks (with patch)', retcode=1) +
    api.step_data('gclient runhooks (without patch)', retcode=1)
  )

  yield (
    api.test('runhooks_failure_ng') +
    api.platform('linux', 64) +
    props(mastername='tryserver.chromium.linux',
          buildername='linux_chromium_rel_ng') +
    api.step_data('gclient runhooks (with patch)', retcode=1)
  )

  yield (
    api.test('compile_failure_ng') +
    api.platform('linux', 64) +
    props(mastername='tryserver.chromium.linux',
          buildername='linux_chromium_rel_ng') +
    suppress_analyze() +
    api.step_data('compile (with patch)', retcode=1)
  )

  # Test that the component rev for v8 is correctly applied
  # both on the initial checkout and after deapplying the patch.
  yield (
    api.test('compile_failure_with_component_rev') +
    api.platform('linux', 64) +
    props(mastername='tryserver.v8',
          buildername='v8_linux_chromium_gn_rel') +
    api.properties(revision='22135') +
    api.override_step_data('read test spec', api.json.output({
        'V8 Linux GN': {
          'additional_compile_targets': ['base_unittests'],
        },
      })
    ) +
    suppress_analyze() +
    api.step_data('compile (with patch)', retcode=1)
  )

  yield (
    api.test('compile_failure_without_patch_ng') +
    api.platform('linux', 64) +
    props(mastername='tryserver.chromium.linux',
          buildername='linux_chromium_rel_ng') +
    suppress_analyze() +
    api.step_data('compile (with patch)', retcode=1) +
    api.step_data('compile (without patch)', retcode=1)
  )

  yield (
    api.test('check_swarming_version_failure') +
    props() +
    api.platform.name('linux') +
    api.step_data('swarming.py --version', retcode=1)
  )

  # Successfully compiling, isolating and running two targets on swarming for a
  # commit queue job.
  yield (
    api.test('swarming_basic_cq') +
    props(requester='commit-bot@chromium.org', blamelist=['joe@chromium.org'],
          extra_swarmed_tests=['base_unittests', 'browser_tests']) +
    api.platform.name('linux') +
    suppress_analyze()
  )

  # Successfully compiling, isolating and running two targets on swarming for a
  # manual try job.
  yield (
    api.test('swarming_basic_try_job') +
    props(buildername='linux_chromium_rel_ng', requester='joe@chromium.org',
          extra_swarmed_tests=['base_unittests', 'browser_tests']) +
    api.platform.name('linux') +
    suppress_analyze()
  )

  # One target (browser_tests) failed to produce *.isolated file.
  yield (
    api.test('swarming_missing_isolated') +
    props(requester='commit-bot@chromium.org', blamelist=['joe@chromium.org'],
          extra_swarmed_tests=['base_unittests']) +
    api.platform.name('linux') +
    suppress_analyze()
  )

  yield (
    api.test('recipe_config_changes_not_retried_without_patch') +
    api.properties.tryserver(
      mastername='tryserver.chromium.linux',
      buildername='linux_chromium_chromeos_rel_ng',
      swarm_hashes={}
    ) +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({
        'Linux ChromiumOS Tests (1)': {
          'gtest_tests': ['base_unittests'],
        },
      })
    ) +
    suppress_analyze() +
    api.override_step_data(
        'git diff to analyze patch',
        api.raw_io.stream_output(
            'testing/buildbot/chromium.chromiumos.json\nfoo/bar/baz.py')
    ) +
    api.override_step_data('base_unittests (with patch)',
                           canned_test(passing=False))
  )

  yield (
    api.test('no_compile_because_of_analyze') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({}))
  )

  # Verifies analyze skips projects other than src.
  yield (
    api.test('dont_analyze_for_non_src_project') +
    props(buildername='linux_chromium_rel_ng') +
    props(patch_project='v8') +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({}))
  )

  # This should result in a compile.
  yield (
    api.test('compile_because_of_analyze_matching_exclusion') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({})) +
    suppress_analyze()
  )

  # This should result in a compile.
  yield (
    api.test('compile_because_of_analyze') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({})) +
    api.override_step_data(
      'analyze',
      api.json.output({'status': 'Found dependency',
                       'compile_targets': [],
                       'test_targets': []}))
  )

  yield (
    api.test('compile_because_of_analyze_with_filtered_tests_no_builder') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data(
      'analyze',
      api.json.output({'status': 'Found dependency',
                       'compile_targets': ['browser_tests', 'base_unittests'],
                       'test_targets': ['browser_tests', 'base_unittests']}))
  )

  yield (
    api.test('compile_because_of_analyze_with_filtered_tests') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data(
      'analyze',
      api.json.output({'status': 'Found dependency',
                       'compile_targets': ['browser_tests', 'base_unittests'],
                       'test_targets': ['browser_tests', 'base_unittests']}))
  )

  # Tests compile_target portion of analyze module.
  yield (
    api.test('compile_because_of_analyze_with_filtered_compile_targets') +
    props(buildername='linux_chromium_rel_ng') +
    api.platform.name('linux') +
    api.override_step_data(
      'analyze',
      api.json.output({'status': 'Found dependency',
                       'test_targets': ['browser_tests', 'base_unittests'],
                       'compile_targets': ['chrome', 'browser_tests',
                                           'base_unittests']}))
  )

  # Tests compile_targets portion of analyze with a bot that doesn't include the
  # 'all' target.
  yield (
    api.test(
      'compile_because_of_analyze_with_filtered_compile_targets_exclude_all') +
    props() +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({
        'Linux Tests': {
          'gtest_tests': ['base_unittests'],
        },
      })
    ) +
    api.override_step_data(
      'analyze',
      api.json.output({'status': 'Found dependency',
                       'test_targets': ['browser_tests', 'base_unittests'],
                       'compile_targets': ['base_unittests']}))
  )

  # Tests compile_targets portion of analyze with a bot that doesn't include the
  # 'all' target.
  yield (
    api.test(
      'analyze_finds_invalid_target') +
    props() +
    api.platform.name('linux') +
    api.override_step_data('read test spec', api.json.output({
        'Linux Tests': {
          'gtest_tests': ['base_unittests'],
        },
      })
    ) +
    api.override_step_data(
      'analyze',
      api.json.output({'invalid_targets': ['invalid target', 'another one']}))
  )

  yield (
    api.test('use_v8_patch_on_chromium_trybot') +
    props(buildername='win_chromium_rel_ng',
          mastername='tryserver.chromium.win',
          patch_project='v8') +
    api.platform.name('win')
  )

  # Tests that we run nothing if analyze said we didn't have to run anything
  # and there were no source file changes.
  yield (
    api.test('analyze_runs_nothing_with_no_source_file_changes') +
    api.properties.tryserver(
      mastername='tryserver.chromium.win',
      buildername='win_chromium_rel_ng',
      swarm_hashes={}
    ) +
    api.platform.name('win') +
    api.override_step_data('analyze', api.chromium.analyze_builds_nothing) +
    api.override_step_data(
        'git diff to analyze patch',
        api.raw_io.stream_output('README.md\nfoo/bar/baz.py')
    )
  )

  yield (
    api.test('analyze_webkit') +
    api.properties.tryserver(
      mastername='tryserver.chromium.win',
      buildername='win_chromium_rel_ng',
      swarm_hashes={}
    ) +
    api.platform.name('win') +
    api.override_step_data(
        'git diff to analyze patch',
        api.raw_io.stream_output(
            'third_party/WebKit/Source/core/dom/Element.cpp\n')
    )
  )

  yield (
    api.test('swarming_paths') +
    api.properties.tryserver(
      mastername='tryserver.chromium.linux',
      buildername='linux_chromium_rel_ng',
      path_config='swarming',
    ) +
    api.platform.name('linux')
  )

  # This tests that if the first fails, but the second pass succeeds
  # that we fail the whole build.
  yield (
    api.test('blink_minimal_pass_continues') +
    props(mastername='tryserver.blink',
          buildername='linux_blink_rel') +
    suppress_analyze() +
    api.platform.name('linux') +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False)) +
    api.override_step_data('webkit_tests (without patch)',
        api.test_utils.canned_test_output(passing=True, minimal=True))
  )

  yield (
    api.test('blink_compile_without_patch_fails') +
    props(mastername='tryserver.blink',
          buildername='linux_blink_rel') +
    suppress_analyze() +
    api.platform.name('linux') +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False)) +
    api.override_step_data('compile (without patch)', retcode=1)
  )

  # This tests what happens if something goes horribly wrong in
  # run-webkit-tests and we return an internal error; the step should
  # be considered a hard failure and we shouldn't try to compare the
  # lists of failing tests.
  # 255 == test_run_results.UNEXPECTED_ERROR_EXIT_STATUS in run-webkit-tests.
  yield (
    api.test('webkit_tests_unexpected_error') +
    props(mastername='tryserver.blink',
          buildername='linux_blink_rel') +
    suppress_analyze() +
    api.platform.name('linux') +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False, retcode=255))
  )

  # TODO(dpranke): crbug.com/357866 . This tests what happens if we exceed the
  # number of failures specified with --exit-after-n-crashes-or-times or
  # --exit-after-n-failures; the step should be considered a hard failure and
  # we shouldn't try to compare the lists of failing tests.
  # 130 == test_run_results.INTERRUPTED_EXIT_STATUS in run-webkit-tests.
  yield (
    api.test('webkit_tests_interrupted') +
    props(mastername='tryserver.blink',
          buildername='linux_blink_rel') +
    suppress_analyze() +
    api.platform.name('linux') +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False, retcode=130))
  )

  # This tests what happens if we don't trip the thresholds listed
  # above, but fail more tests than we can safely fit in a return code.
  # (this should be a soft failure and we can still retry w/o the patch
  # and compare the lists of failing tests).
  yield (
    api.test('too_many_failures_for_retcode') +
    props(mastername='tryserver.blink',
          buildername='linux_blink_rel') +
    suppress_analyze() +
    api.platform.name('linux') +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False,
                                          num_additional_failures=125)) +
    api.override_step_data('webkit_tests (without patch)',
        api.test_utils.canned_test_output(passing=True, minimal=True))
  )

  yield (
    api.test('non_cq_blink_tryjob') +
    props(mastername='tryserver.blink',
          buildername='win_blink_rel',
          requester='someone@chromium.org') +
    suppress_analyze() +
    api.platform.name('win') +
    api.override_step_data('webkit_tests (with patch)',
                           api.test_utils.canned_test_output(passing=True))
  )

  yield (
    api.test('use_v8_patch_on_blink_trybot') +
    props(mastername='tryserver.blink',
          buildername='mac_blink_rel',
          patch_project='v8') +
    api.platform.name('mac')
  )

  yield (
    api.test('use_v8_patch_on_blink_trybot_test_failures') +
    props(mastername='tryserver.v8',
          buildername='v8_linux_blink_rel',
          patch_project='v8') +
    api.platform.name('linux') +
    suppress_analyze(more_exclusions=['v8/f.*']) +
    api.override_step_data('webkit_tests (with patch)',
        api.test_utils.canned_test_output(passing=False)) +
    api.override_step_data('webkit_tests (without patch)',
        api.test_utils.canned_test_output(passing=True, minimal=True))
  )
