# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.types import freeze

DEPS = [
    'adb',
    'chromium',
    'chromium_android',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/step',
]

BUILDERS = freeze({
    'basic_builder': {
        'target': 'Release',
        'build': True,
    },
    'restart_usb_builder': {
        'restart_usb': True,
        'target': 'Release',
        'build': True,
    },
    'coverage_builder': {
        'coverage': True,
        'target': 'Debug',
        'build': True,
    },
    'tester': {},
    'perf_runner': {
        'perf_config': 'sharded_perf_tests.json',
    },
    'perf_runner_user_build': {
        'perf_config': 'sharded_perf_tests.json',
        'skip_wipe': True,
    },
    'perf_runner_disable_location': {
        'perf_config': 'sharded_perf_tests.json',
        'disable_location': True,
    },
    'perf_runner_allow_low_battery': {
        'perf_config': 'sharded_perf_tests.json',
        'min_battery_level': 50,
    },
    'perf_adb_vendor_keys': {
        'adb_vendor_keys': True,
    },
    'perf_runner_allow_high_battery_temp': {
        'perf_config': 'sharded_perf_tests.json',
        'max_battery_temp': 500,
    },
    'gerrit_try_builder': {
        'build': True,
        'skip_wipe': True,
    },
    'java_method_count_builder': {
        'build': True,
        'java_method_count': True,
    },
    'webview_tester': {
        'remove_system_webview': True,
        'disable_system_chrome': True,
    },
    'slow_tester': {
        'timeout_scale': 2,
    },
    'specific_install_tester': {
        'specific_install': True,
    },
    'downgrade_install_tester': {
        'downgrade': True,
    },
    'no_strict_mode_tester': {
        'strict_mode': 'off',
    },
    'resource_size_builder': {
        'resource_size': True,
    },
    'webview_cts': {
        'run_webview_cts': True,
    },
    'last_known_devices': {
      'perf_config': 'sharded_perf_tests.json',
      'last_known_devices': '.last_devices',
    },
    'device_flags_builder': {
      'device_flags': 'device_flags_file',
    }
})

from recipe_engine.recipe_api import Property

PROPERTIES = {
  'buildername': Property(),
}

def RunSteps(api, buildername):
  config = BUILDERS[buildername]

  api.chromium_android.configure_from_properties(
      'base_config',
      REPO_URL='svn://svn.chromium.org/chrome/trunk/src',
      REPO_NAME='src/repo',
      INTERNAL=True,
      BUILD_CONFIG='Release')

  api.chromium_android.c.get_app_manifest_vars = True
  api.chromium_android.c.coverage = config.get('coverage', False)
  api.chromium_android.c.asan_symbolize = True

  if config.get('adb_vendor_keys'):
    # TODO(phajdan.jr): Remove path['build'] usage, http://crbug.com/437264 .
    api.chromium.c.env.ADB_VENDOR_KEYS = api.path['build'].join(
      'site_config', '.adb_key')

  api.chromium_android.init_and_sync(use_bot_update=False)

  api.chromium.runhooks()
  api.chromium_android.run_tree_truth(additional_repos=['foo'])
  assert 'MAJOR' in api.chromium.get_version()

  if config.get('build', False):
    api.chromium.compile()
    api.chromium_android.make_zip_archive('zip_build_proudct', 'archive.zip',
        filters=['*.apk'])
  else:
    api.chromium_android.download_build('build-bucket',
                                              'build_product.zip')
  api.chromium_android.git_number()

  if config.get('java_method_count'):
    api.chromium_android.java_method_count(
        api.chromium.output_dir.join('chrome_public_apk', 'classes.dex.zip'))

  if config.get('specific_install'):
    api.chromium_android.adb_install_apk('Chrome.apk', devices=['abc123'])

  api.adb.root_devices()
  api.chromium_android.spawn_logcat_monitor()

  failure = False
  try:
    # TODO(luqui): remove redundant cruft, need one consistent API.
    api.chromium_android.detect_and_setup_devices()

    api.chromium_android.device_status_check(
      restart_usb=config.get('restart_usb', False))

    api.chromium_android.provision_devices(
        skip_wipe=config.get('skip_wipe', False),
        disable_location=config.get('disable_location', False),
        min_battery_level=config.get('min_battery_level'),
        max_battery_temp=config.get('max_battery_temp'),
        remove_system_webview=config.get('remove_system_webview', False),
        disable_system_chrome=config.get('disable_system_chrome', False))

  except api.step.StepFailure as f:
    failure = f

  if config.get('downgrade'):
    api.chromium_android.adb_install_apk('apk', allow_downgrade=True)

  api.chromium_android.monkey_test()

  try:
    if config.get('perf_config'):
      api.chromium_android.run_sharded_perf_tests(
          config='fake_config.json',
          flaky_config='flake_fakes.json',
          upload_archives_to_bucket='archives-bucket',
          known_devices_file=config.get('last_known_devices', None))
  except api.step.StepFailure as f:
    failure = f

  api.chromium_android.run_instrumentation_suite(
      name='AndroidWebViewTest',
      apk_under_test=api.chromium_android.apk_path('AndroidWebView.apk'),
      test_apk=api.chromium_android.apk_path('AndroidWebViewTest.apk'),
      isolate_file_path='android_webview/android_webview_test_apk.isolate',
      flakiness_dashboard='test-results.appspot.com',
      annotation='SmallTest',
      except_annotation='FlakyTest',
      screenshot=True,
      official_build=True,
      host_driven_root=api.path['checkout'].join('chrome', 'test'),
      timeout_scale=config.get('timeout_scale'),
      strict_mode=config.get('strict_mode'),
      additional_apks=['Additional.apk'],
      device_flags=config.get('device_flags'))
  api.chromium_android.run_test_suite(
      'unittests',
      isolate_file_path=api.path['checkout'].join('some_file.isolate'),
      gtest_filter='WebRtc*',
      tool='asan')
  if not failure:
      api.chromium_android.run_bisect_script(extra_src='test.py',
                                             path_to_config='test.py')

  if config.get('resource_size'):
    api.chromium_android.resource_sizes(
        apk_path=api.chromium_android.apk_path('Chrome.apk'),
        so_path=api.path['checkout'].join(
            'out', api.chromium.c.BUILD_CONFIG, 'chrome_apk', 'libs',
            'armeabi-v7a', 'libchrome.so'),
        so_with_symbols_path=api.path['checkout'].join(
          'out', api.chromium.c.BUILD_CONFIG, 'lib', 'libchrome.so'))

  if config.get('run_webview_cts'):
    api.chromium_android.run_webview_cts()

  api.chromium_android.logcat_dump()
  api.chromium_android.stack_tool_steps()
  if config.get('coverage', False):
    api.chromium_android.coverage_report()

  if failure:
    raise failure

def GenTests(api):
  def properties_for(buildername):
    return api.properties.generic(
        buildername=buildername,
        subordinatename='tehsubordinate',
        repo_name='src/repo',
        patch_url='https://the.patch.url/the.patch',
        repo_url='svn://svn.chromium.org/chrome/trunk/src',
        revision='4f4b02f6b7fa20a3a25682c457bbc8ad589c8a00',
        internal=True)

  for buildername in BUILDERS:
    yield api.test('%s_basic' % buildername) + properties_for(buildername)

  yield (api.test('tester_no_devices') +
         properties_for('tester') +
         api.step_data('device_status_check', retcode=1))

  yield (api.test('tester_other_device_failure') +
         properties_for('tester') +
         api.step_data('device_status_check', retcode=2))

  yield (api.test('tester_with_step_warning') +
         properties_for('tester') +
         api.step_data('unittests', retcode=88))

  yield (api.test('tester_blacklisted_devices') +
         properties_for('tester') +
         api.override_step_data('provision_devices',
                                api.json.output(['abc123', 'def456'])))

  yield (api.test('tester_offline_devices') +
         properties_for('tester') +
         api.override_step_data('device_status_check',
                                api.json.output([{}, {}])))

  yield (api.test('perf_tests_failure') +
      properties_for('perf_runner') +
      api.step_data('perf_test.foo', retcode=1))

  yield (api.test('gerrit_refs') +
      api.properties.generic(
        buildername='gerrit_try_builder',
        subordinatename='testsubordinate',
        repo_name='src/repo',
        patch_url='https://the.patch.url/the.patch',
        repo_url='svn://svn.chromium.org/chrome/trunk/src',
        revision='4f4b02f6b7fa20a3a25682c457bbc8ad589c8a00',
        internal=True, **({'event.patchSet.ref':'refs/changes/50/176150/1'})))

  result_xml_with_unexecuted_tests = """<TestResult>
                          <TestPackage>
                            <TestSuite name='android'>
                              <TestSuite name='webkit'>
                                <TestSuite name='cts'>
                                  <TestCase name='WebSettingsTest'>
                                    <Test name='test' result='notExecuted'>
                                    </Test>
                                  </TestCase>
                                </TestSuite>
                              </TestSuite>
                            </TestSuite>
                          </TestPackage>
                        </TestResult>  """
  yield (api.test('webview_cts_unexecuted_tests') +
         properties_for('webview_cts') +
         api.override_step_data('Run CTS', api.raw_io.stream_output(
             'Created xml report file at file:///path/to/testResult.xml',
             stream='stdout')) + \
         api.override_step_data('Read test result and report failures',
             api.raw_io.output(result_xml_with_unexecuted_tests)))

  result_xml_with_expected_failure = """<TestResult>
                          <TestPackage>
                            <TestSuite name='android'>
                              <TestSuite name='webkit'>
                                <TestSuite name='cts'>
                                  <TestCase name='WebSettingsTest'>
                                    <Test name='testUserAgentString_default'>
                                      <FailedScene> </FailedScene>
                                    </Test>
                                  </TestCase>
                                </TestSuite>
                              </TestSuite>
                            </TestSuite>
                          </TestPackage>
                        </TestResult>  """
  yield (api.test('webview_cts_expected_failure') +
         properties_for('webview_cts') +
         api.override_step_data('Run CTS', api.raw_io.stream_output(
             'Created xml report file at file:///path/to/testResult.xml',
             stream='stdout')) +
         api.override_step_data('Read test result and report failures',
             api.raw_io.output(result_xml_with_expected_failure)))

  result_xml_with_unexpected_failure_class= """<TestResult>
                          <TestPackage>
                            <TestSuite name='android'>
                              <TestSuite name='webkit'>
                                <TestSuite name='cts'>
                                  <TestCase name='unexpected failed classname'>
                                    <Test name='testUserAgentString_default'>
                                      <FailedScene> </FailedScene>
                                    </Test>
                                  </TestCase>
                                </TestSuite>
                              </TestSuite>
                            </TestSuite>
                          </TestPackage>
                        </TestResult>  """
  yield (api.test('webview_cts_unexpected_class_failure') +
         properties_for('webview_cts') +
         api.override_step_data('Run CTS', api.raw_io.stream_output(
             'Created xml report file at file:///path/to/testResult.xml',
             stream='stdout')) +
         api.override_step_data('Read test result and report failures',
              api.raw_io.output(result_xml_with_unexpected_failure_class)))

  result_xml_with_unexpected_failure_method = """<TestResult>
                          <TestPackage>
                            <TestSuite name='android'>
                              <TestSuite name='webkit'>
                                <TestSuite name='cts'>
                                  <TestCase name='WebSettingsTest'>
                                    <Test name='unexpected failed methodname'>
                                      <FailedScene> </FailedScene>
                                    </Test>
                                  </TestCase>
                                </TestSuite>
                              </TestSuite>
                            </TestSuite>
                          </TestPackage>
                        </TestResult>  """
  yield (api.test('webview_cts_unexpected_method_failure') +
         properties_for('webview_cts') +
         api.override_step_data('Run CTS', api.raw_io.stream_output(
             'Created xml report file at file:///path/to/testResult.xml',
             stream='stdout')) +
         api.override_step_data('Read test result and report failures',
             api.raw_io.output(result_xml_with_unexpected_failure_method)))

  yield (api.test('webview_cts_invalid_output') +
         properties_for('webview_cts') +
         api.override_step_data('Run CTS', api.raw_io.stream_output(
             'Invalid CTS output here...',
             stream='stdout')))
