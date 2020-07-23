# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'gitiles',
  'recipe_engine/generator_script',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def _CheckoutSteps(api):
  """Checks out the catapult repo (and any dependencies) using gclient."""
  api.gclient.set_config('catapult')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()


def _FetchAppEngineSDKSteps(api):
  """Fetches the App Engine SDK and returns its path.

  This uses a downloader script in the infra repo to download a script
  which is then used to download and unpack the SDK itself.
  """
  script_content = api.gitiles.download_file(
      'https://chromium.googlesource.com/infra/infra',
      'bootstrap/get_appengine.py',
      step_name='Fetch SDK downloader',
      # This is a commit after the latest fix to the script,
      # which includes retrying requests.
      branch='fd119c547fd4e56eeab77d138b0426022ae1d159')
  api.python.inline('Run SDK downloader', script_content, args=['--dest=.'])
  return api.path['subordinate_build'].join('google_appengine')


def _RemoteSteps(api, app_engine_sdk_path):
  """Runs the build steps specified in catapult_build/build_steps.py.

  Steps are specified in catapult repo in order to avoid multi-sided patches
  when updating tests and adding/moving directories.

  This step uses the generator_script; see documentation at
  github.com/luci/recipes-py/blob/master/recipe_modules/generator_script/api.py

  Use the test_checkout_path property in local tests to run against a local
  copy of catapult_build/build_steps.py.
  """
  base = api.properties.get('test_checkout_path', str(api.path['checkout']))
  script = api.path.join(base, 'catapult_build', 'build_steps.py')
  args = [
      script,
      '--api-path-checkout', api.path['checkout'],
      '--app-engine-sdk-pythonpath', app_engine_sdk_path,
      '--platform', api.platform.name,
  ]
  return api.generator_script(*args)


def RunSteps(api):
  _CheckoutSteps(api)

  # The dashboard unit tests depend on Python modules in the App Engine SDK,
  # and the unit test runner script assumes that the SDK is in PYTHONPATH.
  sdk_path = _FetchAppEngineSDKSteps(api)
  app_engine_sdk_path = api.path.pathsep.join([
      '%(PYTHONPATH)s', str(sdk_path)])
  _RemoteSteps(api, app_engine_sdk_path)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties(mainname='main.client.catapult',
                   buildername='windows',
                   subordinatename='windows_subordinate') +
    api.step_data('Fetch SDK downloader',
                  api.gitiles.make_encoded_file(
                      '"<simulated contents of get_appengine.py>"')) +
    api.generator_script(
      'build_steps.py',
      {'name': 'Dashboard Tests', 'cmd': ['run_py_tests', '--no-hooks']},
    )
  )
