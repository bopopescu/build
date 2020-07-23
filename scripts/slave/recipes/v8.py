# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'archive',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'swarming_client',
  'recipe_engine/time',
  'depot_tools/tryserver',
  'v8',
]


def RunSteps(api):
  v8 = api.v8
  v8.apply_bot_config(v8.BUILDERS)

  additional_trigger_properties = {}
  tests = v8.create_tests()

  if v8.is_pure_swarming_tester(tests):
    api.swarming_client.checkout()

    # Simulate a v8 update on slim swarming testers. The revision
    # property is mandatory.
    api.step.active_result.presentation.properties['got_revision'] = (
        api.properties['revision'])

    v8.set_up_swarming()
  else:
    # Make sure we don't run a non-pure swarming tester on a subdir subordinate.
    # Subdir subordinates have the name pattern 'subordinateN-c3#M'.
    assert '#' not in api.properties.get('subordinatename', ''), (
        'Can only use pure swarming testers on subdir subordinates.')

    if api.platform.is_win:
      api.chromium.taskkill()

    if v8.generate_sanitizer_coverage:
      # When collecting code coverage, we need to resync to the revision that
      # fits to the patch for the line numbers to match.
      v8.checkout(patch=False)
      revision = v8.calculate_patch_base()
      update_step = v8.checkout(revision=revision, suffix='with patch base')
    else:
      update_step = v8.checkout()

    update_properties = update_step.json.output['properties']

    if update_properties.get('got_swarming_client_revision'):
      additional_trigger_properties['parent_got_swarming_client_revision'] = (
          update_properties['got_swarming_client_revision'])

    v8.set_up_swarming()

    if v8.c.mips_cross_compile:
      v8.setup_mips_toolchain()
    v8.runhooks()
    api.chromium.cleanup_temp()

    if v8.generate_gcov_coverage:
      v8.init_gcov_coverage()

    if v8.should_build:
      v8.compile()

    if v8.run_dynamorio:
      v8.dr_compile()

    if v8.should_upload_build:
      v8.upload_build()

    v8.maybe_create_clusterfuzz_archive(update_step)

    if v8.should_download_build:
      v8.download_build()

  if v8.should_test:
    test_results = v8.runtests(tests)
    v8.maybe_bisect(test_results)

    if not api.tryserver.is_tryserver and test_results.is_negative:
      # Let the overall build fail for failures and flakes.
      raise api.step.StepFailure('Failures or flakes in build.')

    if api.tryserver.is_tryserver and test_results.has_failures:
      # Let tryjobs fail for failures only.
      raise api.step.StepFailure('Failures in tryjob.')

  if v8.generate_gcov_coverage:
    v8.upload_gcov_coverage_report()

  v8.maybe_trigger(**additional_trigger_properties)
  v8.verify_cq_integrity()


def GenTests(api):
  for mainname, _, buildername, _ in api.v8.iter_builders():
    yield api.v8.test(mainname, buildername)

  yield (
    api.v8.test(
        'client.v8.branches',
        'V8 Linux - beta branch',
        'branch_sync_failure',
    ) +
    api.step_data('bot_update', retcode=1)
  )

  # Simulate a tryjob triggered by the CQ for setting up different swarming
  # default tags.
  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_rel_ng_triggered',
        'triggered_by_cq',
        requester='commit-bot@chromium.org',
        patch_project='v8',
        blamelist=['dude@chromium.org'],
    )
  )

  # Simulate a tryjob triggered by the tryserver for setting up different
  # swarming default tags.
  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_rel_ng_triggered',
        'triggered_by_ts',
        requester='dude@chromium.org',
        patch_project='v8',
        blamelist=['dude@chromium.org'],
    )
  )

  # Test usage of test filters. They're used when the buildbucket
  # job gets a property 'testfilter', which is expected to be a json list of
  # test-filter strings.
  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_rel_ng_triggered',
        'test_filter',
    ) +
    api.properties(
        testfilter=['mjsunit/regression/*', 'test262/foo', 'test262/bar'],
        extra_flags='--trace_gc --turbo_stats',
    )
  )

  # Test using extra flags with a bot that already uses some extra flags as
  # positional argument.
  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_greedy_allocator_dbg',
        'positional_extra_flags',
    ) +
    api.properties(
        extra_flags=['--trace_gc', '--turbo_stats'],
    )
  )

  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_rel_ng_triggered',
        'failures',
    ) +
    api.v8(test_failures=True, wrong_results=False, flakes=False)
  )

  yield (
    api.v8.test(
        'tryserver.v8',
        'v8_linux_rel_ng_triggered',
        'flakes',
    ) +
    api.v8(test_failures=True, wrong_results=False, flakes=True)
  )

  def TestFailures(wrong_results, flakes):
    results_suffix = "_wrong_results" if wrong_results else ""
    flakes_suffix = "_flakes" if flakes else ""
    return (
      api.v8.test(
          'client.v8',
          'V8 Linux - isolates',
          'test_failures%s%s' % (results_suffix, flakes_suffix),
      ) +
      api.v8(test_failures=True, wrong_results=wrong_results, flakes=flakes)
    )

  yield TestFailures(wrong_results=False, flakes=False)
  yield TestFailures(wrong_results=False, flakes=True)
  yield (
      TestFailures(wrong_results=True, flakes=False) +
      api.expect_exception('AssertionError')
  )

  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - isolates',
        'empty_json',
    ) +
    api.override_step_data('Check', api.json.output([])) +
    api.expect_exception('AssertionError')
  )

  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - isolates',
        'one_failure',
    ) +
    api.override_step_data('Check', api.v8.one_failure())
  )

  yield (
    api.v8.test(
        'client.v8',
        'V8 Fuzzer',
        'fuzz_archive',
    ) +
    api.override_step_data('Fuzz on Ubuntu-12.04', retcode=1)
  )

  # Bisect over range a1, a2, a3. Assume a2 is the culprit. Steps:
  # Bisect a0 -> no failures.
  # Bisect a2 -> failures.
  # Bisect a1 -> no failures.
  # Report culprit a2.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - predictable',
        'bisect',
    ) +
    api.v8.fail('Mjsunit') +
    api.v8.fail('Bisect a2.Retry') +
    api.time.step(120)
  )

  # The same as above, but overriding changes.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - predictable',
        'bisect_override_changes',
    ) +
    api.properties(
        override_changes=[
          {'revision': 'a1'},
          {'revision': 'a2'},
          {'revision': 'a3'},
        ],
    ) +
    api.v8.fail('Mjsunit') +
    api.v8.fail('Bisect a2.Retry') +
    api.time.step(120)
  )

  # Disable bisection, because the failing test is too long compared to the
  # overall test time.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - predictable',
        'bisect_tests_too_long',
    ) +
    api.v8.fail('Mjsunit') +
    api.time.step(7)
  )

  # Bisect over range a1, a2, a3. Assume a2 is the culprit.
  # Same as above with a swarming builder_tester.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - shared',
        'bisect_swarming',
    ) +
    api.v8.fail('Check') +
    api.v8.fail('Bisect a2.Retry') +
    api.time.step(120)
  )

  # Bisect over range a1, a2, a3. Assume a3 is the culprit. This is a tester
  # and the build for a2 is not available. Steps:
  # Bisect a0 -> no failures.
  # Bisect a1 -> no failures.
  # Report a2 and a3 as possible culprits.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux64 - debug - greedy allocator',
        'bisect_tester',
    ) +
    api.v8.fail('Check') +
    api.time.step(120)
  )

  # Same as above with a swarming tester.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux',
        'bisect_tester_swarming',
    ) +
    api.v8.fail('Check') +
    api.time.step(120)
  )

  # Same as above with a slim swarming tester.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux64 - custom snapshot - debug',
        'slim_bisect_tester_swarming',
    ) +
    api.v8.fail('Mjsunit') +
    api.override_step_data(
        'Bisect a0.gsutil download isolated json',
        api.json.output({'mjsunit': '[dummy hash for bisection]'}),
    ) +
    api.override_step_data(
        'Bisect a1.gsutil download isolated json',
        api.json.output({'mjsunit': '[dummy hash for bisection]'}),
    ) +
    api.time.step(120)
  )

  # Disable bisection due to a recurring failure. Steps:
  # Bisect a0 -> failures.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - predictable',
        'bisect_recurring_failure',
    ) +
    api.v8.fail('Mjsunit') +
    api.v8.fail('Bisect a0.Retry') +
    api.time.step(120)
  )

  # Disable bisection due to less than two changes.
  yield (
    api.v8.test(
        'client.v8',
        'V8 Linux - predictable',
        'bisect_one_change',
    ) +
    api.v8.fail('Mjsunit') +
    api.override_step_data(
        'Bisect.Fetch changes', api.v8.example_one_buildbot_change()) +
    api.override_step_data(
        'Bisect.Get change range',
        api.v8.example_bisection_range_one_change(),
    ) +

    api.time.step(120)
  )
