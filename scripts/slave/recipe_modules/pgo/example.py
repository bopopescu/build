# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Example of using the PGO recipe module."""

# Recipe module dependencies.
DEPS = [
  'recipe_engine/platform',
  'recipe_engine/properties',
  'pgo',
]

from recipe_engine import recipe_test_api
from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze


PROPERTIES = {
  'buildername': Property(),
}


TEST_BUILDERS = freeze({
  'chromium_pgo.test' : {
    'Test builder': {
      'recipe_config': 'chromium',
      'chromium_config_instrument': 'chromium_pgo_instrument',
      'chromium_config_optimize': 'chromium_pgo_optimize',
      'gclient_config': 'chromium',
      'clobber': True,
      'patch_root': 'src',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
      },
      'testing': {
        'platform': 'win',
      },
    },
  }
})


def RunSteps(api, buildername):
  buildername = api.properties['buildername']
  mainname = api.properties['mainname']
  bot_config = TEST_BUILDERS.get(mainname, {}).get(buildername)

  api.pgo.compile_pgo(bot_config)


def GenTests(api):
  def _sanitize_nonalpha(text):
    return ''.join(c if c.isalnum() else '_' for c in text)

  for mainname, builders in TEST_BUILDERS.iteritems():
    for buildername in builders:
      yield (
        api.test('full_%s_%s' % (_sanitize_nonalpha(mainname),
                                 _sanitize_nonalpha(buildername))) +
        api.properties.generic(mainname=mainname, buildername=buildername) +
        api.platform('win', 64)
      )

  yield (
    api.test('full_%s_%s_benchmark_failure' %
        (_sanitize_nonalpha('chromium_pgo.test'),
         _sanitize_nonalpha('Test builder'))) +
    api.properties.generic(mainname='chromium_pgo.test',
                           buildername='Test builder') +
    api.platform('win', 32) +
    api.step_data('Telemetry benchmark: sunspider', retcode=1)
  )
