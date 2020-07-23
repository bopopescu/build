# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def RunSteps(api):
  api.gclient.set_config('wasm_llvm')
  result = api.bot_update.ensure_checkout(force=True)
  got_revision = result.presentation.properties['got_waterfall_revision']

  env = {
      'BUILDBOT_MASTERNAME': api.properties['mainname'],
      'BUILDBOT_BUILDERNAME': api.properties['buildername'],
      'BUILDBOT_REVISION': api.properties['revision'],
      'BUILDBOT_GOT_WATERFALL_REVISION': got_revision,
  }
  api.python('annotated steps',
             api.path['checkout'].join('src', 'build.py'),
             allow_subannotations=True,
             cwd=api.path['checkout'],
             env = env)


def GenTests(api):
  yield (
    api.test('linux') +
    api.properties(
      mainname = 'client.wasm.llvm',
      buildername = 'linux',
      subordinatename = 'TestSubordinatename',
      revision = 'abcd',
    ))
