# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'depot_tools/tryserver',
]


def RunSteps(api):
  api.chromium.set_config('chromium')
  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout(force=True)
  api.tryserver.maybe_apply_issue()
  api.chromium.runhooks()
  api.chromium.cleanup_temp()
  api.chromium.compile(['chromium_builder_tests'])
  api.python(
      'annotated_steps',
      api.path['build'].join(
          'scripts', 'subordinate', 'chromium', 'nacl_sdk_buildbot_run.py'),
      allow_subannotations=True)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic() +
    api.platform('linux', 64)
  )
