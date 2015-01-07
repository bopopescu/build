# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'adb',
  'chromium',
  'chromium_android',
  'chromium_tests',
  'isolate',
  'json',
  'path',
  'platform',
  'properties',
  'python',
  'test_utils',
  'step',
  'swarming',
]


def GenSteps(api):
  mastername = api.properties.get('mastername')
  buildername = api.properties.get('buildername')

  update_step, master_dict, test_spec = \
      api.chromium_tests.sync_and_configure_build(mastername, buildername)
  api.chromium_tests.compile(mastername, buildername, update_step, master_dict,
                             test_spec)
  tests = api.chromium_tests.tests_for_builder(
      mastername, buildername, update_step, master_dict)

  if not tests:
    return

  api.chromium_tests.configure_swarming('chromium', precommit=False)
  test_runner = api.chromium_tests.create_test_runner(api, tests)
  api.chromium_tests.setup_chromium_tests(test_runner, mastername=mastername)


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  for mastername, master_config in api.chromium.builders.iteritems():

    # parent builder name -> list of triggered builders.
    triggered_by_parent = {}
    for buildername, bot_config in master_config['builders'].iteritems():
      parent = bot_config.get('parent_buildername')
      if parent:
        triggered_by_parent.setdefault(parent, []).append(buildername)

    for buildername, bot_config in master_config['builders'].iteritems():
      bot_type = bot_config.get('bot_type', 'builder_tester')

      if bot_type in ['builder', 'builder_tester']:
        assert bot_config.get('parent_buildername') is None, (
            'Unexpected parent_buildername for builder %r on master %r.' %
                (buildername, mastername))

      test = (
        api.test('full_%s_%s' % (_sanitize_nonalpha(mastername),
                                 _sanitize_nonalpha(buildername))) +
        api.properties.generic(mastername=mastername,
                               buildername=buildername,
                               parent_buildername=bot_config.get(
                                   'parent_buildername')) +
        api.platform(bot_config['testing']['platform'],
                     bot_config.get(
                         'chromium_config_kwargs', {}).get('TARGET_BITS', 64))
      )
      if bot_config.get('parent_buildername'):
        test += api.properties(parent_got_revision='1111111')
        test += api.properties(
            parent_build_archive_url='gs://test-domain/test-archive.zip')

      if (bot_type in ['builder', 'builder_tester'] and
          bot_config['testing']['platform'] == 'linux'):
        test += api.step_data('checkdeps', api.json.output([]))

      if mastername == 'client.v8':
        test += api.properties(revision='22135')

      if bot_config.get('enable_swarming'):
        if bot_type in 'tester':
          test += api.properties(swarm_hashes={
            'browser_tests': 'ffffffffffffffffffffffffffffffffffffffff',
          })

        builders_with_tests = []
        if bot_type == 'builder':
          builders_with_tests = triggered_by_parent.get(buildername, [])
        else:
          builders_with_tests = [buildername]

        test += api.override_step_data('read test spec', api.json.output({
            b: {
            'gtest_tests': [
              {
                'test': 'browser_tests',
                'swarming': {'can_use_on_swarming_builders': True},
              },
            ],
          } for b in builders_with_tests
        }))

      yield test

  yield (
    api.test('dynamic_gtest') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Tests',
                           parent_buildername='Linux Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux Tests': {
        'gtest_tests': [
          'base_unittests',
          {'test': 'browser_tests', 'shard_index': 0, 'total_shards': 2},
        ],
      },
    }))
  )

  yield (
    api.test('dynamic_swarmed_gtest') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux Tests': {
        'gtest_tests': [
          {'test': 'browser_tests',
           'swarming': {'can_use_on_swarming_builders': True}},
        ],
      },
    }))
  )

  yield (
    api.test('dynamic_gtest_on_builder') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux Tests': {
        'gtest_tests': [
          'base_unittests',
          {'test': 'browser_tests', 'shard_index': 0, 'total_shards': 2},
        ],
      },
    }))
  )

  yield (
    api.test('dynamic_gtest_win') +
    api.properties.generic(mastername='chromium.win',
                           buildername='Win7 Tests (1)',
                           parent_buildername='Win Builder') +
    api.platform('win', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Win7 Tests (1)': {
        'gtest_tests': [
          'aura_unittests',
          {'test': 'browser_tests', 'shard_index': 0, 'total_shards': 2},
        ],
      },
    }))
  )

  # Tests switching on asan and swiching off lsan for sandbox tester.
  yield (
    api.test('dynamic_gtest_memory') +
    api.properties.generic(mastername='chromium.memory',
                           buildername='Linux ASan Tests (sandboxed)',
                           parent_buildername='Linux ASan LSan Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux ASan Tests (sandboxed)': {
        'gtest_tests': [
          'browser_tests',
        ],
      },
    }))
  )

  # Tests that the memory builder is using the correct compile targets.
  yield (
    api.test('dynamic_gtest_memory_builder') +
    api.properties.generic(mastername='chromium.memory',
                           buildername='Linux ASan LSan Builder',
                           revision='123456') +
    api.platform('linux', 64) +
    # The builder should build 'browser_tests', because there exists a child
    # tester that uses that test.
    api.override_step_data('read test spec', api.json.output({
      'Linux ASan Tests (sandboxed)': {
        'gtest_tests': [
          'browser_tests',
        ],
      },
    }))
  )

  # Tests that the memory mac tester is using the correct test flags.
  yield (
    api.test('dynamic_gtest_memory_mac64') +
    api.properties.generic(
        mastername='chromium.memory',
        buildername='Mac ASan 64 Tests (1)',
        parent_buildername='Mac ASan 64 Builder') +
    api.platform('mac', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Mac ASan 64 Tests (1)': {
        'gtest_tests': [
          'browser_tests',
        ],
      },
    }))
  )

  yield (
    api.test('arm') +
    api.properties.generic(mastername='chromium.fyi',
                           buildername='Linux ARM Cross-Compile') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux ARM Cross-Compile': {
        'compile_targets': ['browser_tests_run'],
        'gtest_tests': [{
          'test': 'browser_tests',
          'args': ['--gtest-filter', '*NaCl*.*'],
          'shard_index': 0,
          'total_shards': 1,
        }],
      },
    }))
  )

  yield (
    api.test('findbugs_failure') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Android Builder (dbg)') +
    api.platform('linux', 32) +
    api.step_data('findbugs', retcode=1)
  )

  yield (
    api.test('msan') +
    api.properties.generic(mastername='chromium.memory.fyi',
                           buildername='Linux MSan Tests',
                           parent_buildername='Chromium Linux MSan Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux MSan Tests': {
        'compile_targets': ['base_unittests'],
        'gtest_tests': ['base_unittests'],
      },
    }))
  )

  yield (
    api.test('buildnumber_zero') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Tests',
                           parent_buildername='Linux Builder',
                           buildnumber=0) +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux Tests': {
        'gtest_tests': [
          'base_unittests',
          {'test': 'browser_tests', 'shard_index': 0, 'total_shards': 2},
        ],
      },
    }))
  )

  # FIXME(iannucci): Make this test work.
  #yield (
  #  api.test('one_failure_keeps_going') +
  #  api.properties.generic(mastername='chromium.linux',
  #                         buildername='Linux Tests',
  #                         parent_buildername='Linux Builder') +
  #  api.platform('linux', 64) +
  #  api.step_data('mojo_python_tests', retcode=1)
  #)

  yield (
    api.test('one_failure_keeps_going_dynamic_tests') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Tests',
                           parent_buildername='Linux Builder') +
    api.platform('linux', 64) +
    api.override_step_data('read test spec', api.json.output({
      'Linux Tests': {
        'gtest_tests': [
          'base_unittests',
          {'test': 'browser_tests', 'shard_index': 0, 'total_shards': 2},
        ],
      },
    })) +
    api.step_data('base_unittests', retcode=1)
  )

  yield (
    api.test('ios_gfx_unittests_failure') +
    api.properties.generic(mastername='chromium.mac',
                           buildername='iOS Simulator (dbg)') +
    api.platform('mac', 32) +
    api.override_step_data(
        'gfx_unittests', api.json.canned_gtest_output(True), retcode=1)
  )

  yield (
    api.test('archive_dependencies_failure') +
    api.properties.generic(mastername='chromium.linux',
                           buildername='Linux Builder',
                           buildnumber=0) +
    api.platform('linux', 64) +
    api.override_step_data(
        'archive dependencies', api.json.canned_gtest_output(True), retcode=1)
  )

  yield (
    api.test('perf_test_profile_failure') +
    api.properties.generic(mastername='chromium.perf',
                           buildername='Linux Perf (1)',
                           parent_buildername='Linux Builder',
                           buildnumber=0) +
    api.platform('linux', 64) +
    api.override_step_data(
        'blink_perf.all.release',
        api.json.output([]),
        retcode=1)
  )
