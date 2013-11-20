# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromium',
  'gclient',
  'python',
  'path',
  'step',
]

OZONE_TESTS = [
    # Linux tests.
    'base_unittests',
    # 'browser_tests', Not sensible.
    'cacheinvalidation_unittests',
    'cc_unittests',
    'components_unittests',
    'content_browsertests',
    'content_unittests',
    'crypto_unittests',
    'dbus_unittests',
    'device_unittests',
    # 'google_apis_unittests', Not sensible.
    'gpu_unittests',
    # 'interactive_ui_tests', Not sensible.
    'ipc_tests',
    # 'jingle_unittests', Later.
    'media_unittests',
    'net_unittests',
    'ppapi_unittests',
    # 'printing_unittests', Not sensible.
    'sandbox_linux_unittests',
    'sql_unittests',
    'sync_unit_tests',
    'ui_unittests',
    # 'unit_tests',  Not sensible.
    'url_unittests',
    # 'webkit_compositor_bindings_unittests', Not specified in bug.
    # 'sync_integration_tests', Not specified in bug.
    # 'chromium_swarm_tests', Not specified in bug.
] + [
    'aura_unittests',
    'compositor_unittests',
]

tests_that_do_not_compile = [
    'compositor_unittests',  # Bug 315370, ...
]

tests_that_do_not_pass = [
    'content_browsertests',  # Bug 315392, ...
]

dbus_tests = [
    'dbus_unittests',
]

def GenSteps(api):

  api.chromium.set_config('chromium', BUILD_CONFIG='Debug')

  yield api.gclient.checkout()

  api.chromium.c.gyp_env.GYP_DEFINES['embedded'] = 1
  api.chromium.c.gyp_env.GYP_DEFINES['component'] = 'static_library'

  yield api.chromium.runhooks()
  yield api.chromium.compile(['content_shell'], name='compile content_shell')

  yield api.python('check ecs deps', api.path.checkout('tools',
      'check_ecs_deps', 'check_ecs_deps.py'),
      can_fail_build=False,
      cwd=api.chromium.c.build_dir(api.chromium.c.build_config_fs))

  tests_to_compile = list(set(OZONE_TESTS) - set(tests_that_do_not_compile))
  tests_to_compile.sort()
  yield api.chromium.compile(tests_to_compile, name='compile tests')

  tests_to_run = list(set(tests_to_compile) - set(tests_that_do_not_pass))
  yield (api.chromium.runtests(x, xvfb=False, spawn_dbus=(x in dbus_tests))
         for x in sorted(tests_to_run))

  # Compile the failing targets.
  yield (api.chromium.compile([x], name='experimentally compile %s' % x,
                              can_fail_build=False, abort_on_failure=False,
                              always_run=True)
         for x in sorted(set(OZONE_TESTS) & set(tests_that_do_not_compile)))

  # Run the failing tests.
  tests_to_try = list(set(tests_to_compile) & set(tests_that_do_not_pass))
  yield (api.chromium.runtests(x, xvfb=False, name='experimentally run %s' % x,
                               can_fail_build=False)
         for x in sorted(tests_to_try))


def GenTests(api):
  yield api.test('basic')
