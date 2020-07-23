# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/properties',
]


def _CheckoutSteps(api):
  # Checkout custom-tabs-client. The config is implemented at:
  #   scripts/subordinate/recipe_modules/gclient/config.py
  api.gclient.set_config('custom_tabs_client')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()


def RunSteps(api):
  _CheckoutSteps(api)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties(mainname='main.tryserver.client.custom_tabs_client',
                   buildername='linux',
                   subordinatename='linux_subordinate')
  )
