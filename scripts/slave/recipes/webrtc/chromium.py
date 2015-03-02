# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Recipe for building Chromium and running WebRTC-specific tests with special
# requirements that doesn't allow them to run in the main Chromium waterfalls.
# Also provide a set of FYI bots that builds Chromium with WebRTC ToT to provide
# pre-roll test results.

DEPS = [
  'archive',
  'bot_update',
  'chromium',
  'chromium_android',
  'chromium_tests',
  'gclient',
  'json',
  'path',
  'platform',
  'properties',
  'python',
  'webrtc',
]


def GenSteps(api):
  mastername = api.properties.get('mastername')
  buildername = api.properties.get('buildername')
  master_dict = api.webrtc.BUILDERS.get(mastername, {})
  master_settings = master_dict.get('settings', {})
  bot_config = master_dict.get('builders', {}).get(buildername)
  assert bot_config, ('Unrecognized builder name "%r" for master "%r".' %
                      (buildername, mastername))
  recipe_config_name = bot_config['recipe_config']
  recipe_config = api.webrtc.RECIPE_CONFIGS.get(recipe_config_name)
  assert recipe_config, ('Cannot find recipe_config "%s" for builder "%r".' %
                         (recipe_config_name, buildername))

  api.webrtc.setup(bot_config, recipe_config,
                   master_settings.get('PERF_CONFIG'))

  if api.platform.is_win:
    api.chromium.taskkill()

  bot_type = bot_config.get('bot_type', 'builder_tester')

  api.webrtc.checkout()
  api.webrtc.cleanup()
  if not bot_config.get('disable_runhooks'):
    api.chromium.runhooks()

  if bot_type in ('builder', 'builder_tester'):
    run_gn = api.chromium.c.project_generator.tool == 'gn'
    if run_gn:
      api.chromium.run_gn(use_goma=True)

    compile_targets = recipe_config.get('compile_targets', [])
    api.chromium.compile(targets=compile_targets)
    if (mastername == 'chromium.webrtc.fyi' and not run_gn and
        api.chromium.c.TARGET_PLATFORM != 'android'):
      api.webrtc.sizes()

  if bot_type == 'builder' and bot_config.get('build_gs_archive'):
    api.webrtc.package_build(
        api.webrtc.GS_ARCHIVES[bot_config['build_gs_archive']])

  if bot_type == 'tester':
    api.webrtc.extract_build(
        api.webrtc.GS_ARCHIVES[bot_config['build_gs_archive']])

  if bot_type in ('builder_tester', 'tester'):
    if api.chromium.c.TARGET_PLATFORM == 'android':
      api.chromium_android.common_tests_setup_steps()
      api.chromium_android.run_test_suite(
          'content_browsertests',
          gtest_filter='WebRtc*')
      api.chromium_android.common_tests_final_steps()
    else:
      api.chromium_tests.setup_chromium_tests(api.webrtc.runtests)


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  builders = api.webrtc.BUILDERS

  def generate_builder(mastername, buildername, revision=None,
                       failing_test=None, parent_got_revision=None,
                       suffix=None):
    suffix = suffix or ''
    bot_config = builders[mastername]['builders'][buildername]
    bot_type = bot_config.get('bot_type', 'builder_tester')

    if bot_type in ('builder', 'builder_tester'):
      assert bot_config.get('parent_buildername') is None, (
          'Unexpected parent_buildername for builder %r on master %r.' %
              (buildername, mastername))
    test = (
      api.test('%s_%s%s' % (_sanitize_nonalpha(mastername),
                            _sanitize_nonalpha(buildername), suffix)) +
      api.properties.generic(mastername=mastername,
                             buildername=buildername,
                             revision=revision,
                             parent_buildername=bot_config.get(
                                 'parent_buildername')) +
      api.platform(bot_config['testing']['platform'],
                   bot_config.get(
                       'chromium_config_kwargs', {}).get('TARGET_BITS', 64))
    )
    if bot_type == 'tester':
      parent_rev = parent_got_revision or revision
      test += api.properties(parent_got_revision=parent_rev)

    if failing_test:
      test += api.step_data(failing_test, retcode=1)

    return test

  for mastername in ('chromium.webrtc', 'chromium.webrtc.fyi'):
    master_config = builders[mastername]
    for buildername in master_config['builders'].keys():
      revision = '12345' if mastername == 'chromium.webrtc.fyi' else '321321'
      yield generate_builder(mastername, buildername, revision)

  # Forced build (not specifying any revision) and failing tests.
  mastername = 'chromium.webrtc'
  yield generate_builder(mastername, 'Linux Builder', revision=None,
                         suffix='_forced')

  buildername = 'Linux Tester'
  yield generate_builder(mastername, buildername, revision=None,
                         suffix='_forced_invalid')
  yield generate_builder(mastername, buildername, revision='321321',
                         failing_test='browser_tests', suffix='_failing_test')

  # Periodic scheduler triggered builds also don't contain revision.
  mastername = 'chromium.webrtc.fyi'
  yield generate_builder(mastername, 'Win Builder', revision=None,
                         suffix='_periodic_triggered')

  # Testers gets got_revision value from builder passed as parent_got_revision.
  yield generate_builder(mastername, 'Win7 Tester', revision=None,
                         parent_got_revision='12345',
                         suffix='_periodic_triggered')
