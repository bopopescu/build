# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('chromium')
  api.chromium.set_config('ninja')

  api.bot_update.ensure_checkout(force=True)

  api.python(
      'run_tests',
      api.path['checkout'].join('third_party', 'closure_compiler',
                                'run_tests.py')
  )

  api.step(
      'generate_gyp_files',
      [api.path['checkout'].join('build', 'gyp_chromium'),
       api.path['checkout'].join('third_party', 'closure_compiler',
                                 'compiled_resources.gyp')],
  )

  api.chromium.compile()

  api.step(
      'generate_v2_gyp_files',
      [api.path['checkout'].join('build', 'gyp_chromium'),
       api.path['checkout'].join('third_party', 'closure_compiler',
                                 'compiled_resources2.gyp')],
  )

  api.chromium.compile(name='compile_v2')


def GenTests(api):
  yield (
    api.test('main') +
    api.properties.generic(
      mainname='chromium.fyi',
      buildername='Closure Compilation Linux',
    )
  )
