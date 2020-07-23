# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def _CheckoutSteps(api, buildername):
  """Checks out the catapult repo (and any dependencies) using gclient."""
  api.gclient.set_config('catapult')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()


def RunSteps(api):
  buildername = api.properties.get('buildername')
  _CheckoutSteps(api, buildername)

  api.python('chromium.perf success rates',
             api.path['checkout'].join('catapult_base', 'catapult_base',
                                       'perfbot_stats', 'chrome_perf_stats.py'))


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties(mainname='main.client.catapult',
                   buildername='linux',
                   subordinatename='linux_subordinate')
  )
