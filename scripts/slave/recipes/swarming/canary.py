# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Swarming canary recipe: runs tests for HEAD of chromium using HEAD of
swarming_client toolset on Swarming canary server instances (*-dev.appspot.com).

Intended to catch bugs in swarming_client and Swarming servers early on, before
full roll out.

Waterfall page: https://build.chromium.org/p/chromium.swarm/waterfall
"""

DEPS = [
  'bot_update',
  'chromium',
  'gclient',
  'isolate',
  'json',
  'platform',
  'properties',
  'step',
  'swarming',
  'swarming_client',
  'test_utils',
]


def GenSteps(api):
  # Configure isolate & swarming modules to use canary instances.
  api.isolate.isolate_server = 'https://isolateserver-dev.appspot.com'
  api.swarming.swarming_server = 'https://chromium-swarm-dev.appspot.com'
  api.swarming.profile = True
  api.swarming.verbose = True

  # Run tests from chromium.swarm buildbot with a relatively high priority
  # so that they take precedence over manually triggered tasks.
  api.swarming.task_priority = 20

  # We are building simplest Chromium flavor possible.
  api.chromium.set_config(
      'chromium', BUILD_CONFIG=api.properties.get('configuration', 'Release'))

  # We are checking out Chromium with swarming_client dep unpinned and pointing
  # to ToT of swarming_client repo, see recipe_modules/gclient/config.py.
  api.gclient.set_config('chromium')
  api.gclient.c.solutions[0].custom_vars['swarming_revision'] = ''
  api.gclient.c.revisions['src/tools/swarming_client'] = 'HEAD'

  # Enable test isolation. Modifies GYP_DEFINES used in 'runhooks' below.
  api.isolate.set_isolate_environment(api.chromium.c)

  # Checkout chromium + deps (including 'master' of swarming_client).
  step_result = api.bot_update.ensure_checkout()
  if not step_result.json.output['did_run']:
    api.gclient.checkout()

  # Ensure swarming_client version is fresh enough.
  api.swarming.check_client_version()

  # Build all supported tests, isolate them to the server. Set ISOLATE_DEBUG so
  # that isolate scripts invoked by ninja produce more information. Corresponds
  # to --profile flag.
  api.chromium.runhooks()
  api.isolate.clean_isolated_files(api.chromium.output_dir)
  api.chromium.compile(
      targets=['chromium_swarm_tests'], env={'ISOLATE_DEBUG': 1})

  # Gather hashes of all isolated tests.
  api.isolate.find_isolated_tests(api.chromium.output_dir)

  # Make swarming tasks that run isolated tests.
  tasks = [
    api.swarming.gtest_task(
        test,
        isolated_hash,
        shards=2,
        test_launcher_summary_output=api.json.gtest_results(add_json_log=False))
    for test, isolated_hash in sorted(api.isolate.isolated_tests.iteritems())
  ]

  # Launch them on swarming using OS dimension that correspond to platform this
  # recipe is running on (that is default behavior), since we used that platform
  # to compile tests.
  for task in tasks:
    api.swarming.trigger_task(task)

  # And wait for ALL them to finish.
  with api.step.defer_results():
    for task in tasks:
      api.swarming.collect_task(task)


def GenTests(api):
  for platform in ('linux', 'win', 'mac'):
    for configuration in ('Debug', 'Release'):
      yield (
        api.test('%s_%s' % (platform, configuration)) +
        api.platform.name(platform) +
        api.properties.scheduled() +
        api.properties(configuration=configuration)
      )

  # One 'collect' fails due to a missing shard and failing test, should not
  # prevent the second 'collect' from running.
  yield (
    api.test('one_fails') +
    api.platform.name('linux') +
    api.properties.scheduled() +
    api.properties(configuration='Debug') +
    api.override_step_data(
        'dummy_target_1',
        api.json.canned_gtest_output(
            passing=False,
            minimal=True,
            extra_json={'missing_shards': [1]}),
    )
  )
