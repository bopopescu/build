# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'file',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('infradata_main_manager')
  api.bot_update.ensure_checkout(
      force=True, patch_root='infra-data-main-manager', patch_oauth2=True)
  api.gclient.runhooks()

  api.python('main manager configuration test',
             api.path['subordinate_build'].join('infra', 'run.py'),
             ['infra.services.main_manager_launcher',
              '--verify',
              '--ts-mon-endpoint=none',
              '--json-file',
             api.path['subordinate_build'].join(
                 'infra-data-main-manager',
                 'desired_main_state.json')])


def GenTests(api):
  yield (
      api.test('main_manager_config') +
      api.properties.git_scheduled(
          buildername='infradata_config',
          buildnumber=123,
          mainname='internal.infra',
          repository='https://chrome-internal.googlesource.com/infradata'))
  yield (
      api.test('main_manager_config_patch') +
      api.properties.git_scheduled(
          buildername='infradata_config',
          buildnumber=123,
          mainname='internal.infra.try',
          patch_project='infra-data-configs',
          repository='https://chrome-internal.googlesource.com/infradata'))
