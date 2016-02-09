# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from recipe_engine.types import freeze
from recipe_engine import recipe_api

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'chromium_android',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

BUILDERS = freeze({
  'chromium.mojo': {
    'builders': {
      'Chromium Mojo Linux': {
        'chromium_config_kwargs': {
          'BUILD_CONFIG': 'Release',
          'TARGET_PLATFORM': 'linux',
        },
      },
      'Chromium Mojo Android': {
        'chromium_config': 'android',
        'chromium_config_kwargs': {
          'BUILD_CONFIG': 'Release',
          'TARGET_PLATFORM': 'android',
          'TARGET_ARCH': 'arm',
          'TARGET_BITS': 32,
        },
        'gclient_apply_config': ['android'],
      },
      'Chromium Mojo Windows': {
        'chromium_config_kwargs': {
          'BUILD_CONFIG': 'Release',
          'TARGET_PLATFORM': 'win',
        },
      },
    },
  },
})


@recipe_api.composite_step
def _RunApptests(api):
  # TODO(msw): Run and get compile targets via testing/scripts/mojo_apptests.py.
  runner = api.path['checkout'].join('mojo', 'tools', 'apptest_runner.py')
  api.python('app_tests', runner, [api.chromium.output_dir, '--verbose'])


def _RunUnitAndAppTests(api):
  with api.step.defer_results():
    api.chromium.runtest('ipc_mojo_unittests')
    api.chromium.runtest('mojo_common_unittests')

    # TODO(yzshen): fix missing JS files on Android. crbug.com/536669
    if api.chromium.c.TARGET_PLATFORM != 'android':
      api.chromium.runtest('mojo_js_integration_tests')
      api.chromium.runtest('mojo_js_unittests')

    api.chromium.runtest('mojo_public_application_unittests')
    api.chromium.runtest('mojo_public_bindings_unittests')
    api.chromium.runtest('mojo_public_environment_unittests')
    api.chromium.runtest('mojo_public_system_unittests')
    api.chromium.runtest('mojo_public_utility_unittests')
    api.chromium.runtest('mojo_runner_host_unittests')
    api.chromium.runtest('mojo_shell_unittests')
    api.chromium.runtest('mojo_surfaces_lib_unittests')
    api.chromium.runtest('mojo_system_unittests')
    api.chromium.runtest('mojo_view_manager_lib_unittests')
    api.chromium.runtest('resource_provider_unittests')
    api.chromium.runtest('window_manager_unittests')
    _RunApptests(api)


def RunSteps(api):
  api.chromium.configure_bot(BUILDERS, ['gn'])

  api.bot_update.ensure_checkout(force=True)

  api.chromium.runhooks()

  api.chromium.run_mb(api.properties.get('mastername'),
                      api.properties.get('buildername'),
                      use_goma=True)

  api.chromium.compile(targets=['mojo:tests', 'mojo_apptests'])

  if api.chromium.c.TARGET_PLATFORM == 'android':
    api.chromium_android.detect_and_setup_devices()

  _RunUnitAndAppTests(api)


def GenTests(api):
  for test in api.chromium.gen_tests_for_builders(BUILDERS):
    yield test
