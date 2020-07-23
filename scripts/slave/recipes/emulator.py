# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api
from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'chromium_android',
  'emulator',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',
]

REPO_URL = 'https://chromium.googlesource.com/chromium/src.git'

UNITTESTS = freeze([
  ['android_webview_unittests', None],
  ['base_unittests', ['base', 'base_unittests.isolate']],
  ['cc_unittests', None],
  ['components_unittests', ['components', 'components_unittests.isolate']],
  ['events_unittests', None],
  ['gl_tests', None],
  ['ipc_tests', None],
  ['skia_unittests', None],
  ['sql_unittests', ['sql', 'sql_unittests.isolate']],
  ['sync_unit_tests', ['sync', 'sync_unit_tests.isolate']],
  ['ui_android_unittests', None],
  ['ui_touch_selection_unittests', None],
])

BUILDERS = freeze({
  'chromium.fyi':{
    'Android Tests (x86 emulator)': {
      'config': 'x86_builder_mb',
      'target': 'Debug',
      'abi': 'x86',
      'api_level': 23,
      'unittests': UNITTESTS,
      'sdcard_size': '500M',
      'storage_size': '1024M'
    }
  }
})


PROPERTIES = {
  'buildername': Property(),
  'mainname': Property(),
}

def RunSteps(api, mainname, buildername):
  builder = BUILDERS[mainname][buildername]
  api.chromium_android.configure_from_properties(
      builder['config'],
      REPO_NAME='src',
      REPO_URL=REPO_URL,
      INTERNAL=False,
      BUILD_CONFIG=builder['target'])

  api.gclient.set_config('chromium')
  api.gclient.apply_config('android')
  api.emulator.set_config('base_config')

  api.bot_update.ensure_checkout()
  api.chromium_android.clean_local_files()
  api.chromium.runhooks()

  if api.chromium.c.project_generator.tool == 'mb':
    api.chromium.run_mb(mainname, buildername, use_goma=True)

  targets = []
  for target, _ in builder.get('unittests', []):
    targets.append(target + '_apk')
  api.chromium.compile(targets=targets)

  api.emulator.install_emulator_deps(api_level=builder.get('api_level'))

  provision_settings = builder.get('provision_provision_settings', {})

  default_emulator_amount = 1
  with api.emulator.launch_emulator(
      abi=builder.get('abi'),
      api_level=builder.get('api_level'),
      amount=builder.get('amount', default_emulator_amount),
      partition_size=builder.get('partition_size'),
      sdcard_size=builder.get('sdcard_size')):
    api.emulator.wait_for_emulator(builder.get('amount',
                                               default_emulator_amount))
    api.chromium_android.spawn_logcat_monitor()
    api.chromium_android.provision_devices(emulators=True, **provision_settings)

    try:
      with api.step.defer_results():
        for suite, isolate_file in builder.get('unittests', []):
          isolate_file_path = (
              api.path['checkout'].join(*isolate_file)
              if isolate_file else None)
          api.chromium_android.run_test_suite(
              suite, isolate_file_path=isolate_file_path)
    finally:
      api.chromium_android.logcat_dump()
      api.chromium_android.stack_tool_steps()
      api.chromium_android.test_report()

def GenTests(api):
  sanitize = lambda s: ''.join(c if c.isalnum() else '_' for c in s)

  for mainname in BUILDERS:
    main = BUILDERS[mainname]
    for buildername in main:
      yield (
          api.test('%s_test_basic' % sanitize(buildername)) +
          api.properties.generic(
              buildername=buildername,
              mainname=mainname))

  yield (
      api.test('Android_Tests__x86_emulator__test_fail') +
      api.properties.generic(
        buildername='Android Tests (x86 emulator)',
        mainname='chromium.fyi') +
      api.step_data('android_webview_unittests', retcode=2)
  )
