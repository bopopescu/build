# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.types import freeze

DEPS = [
  'archive',
  'chromium',
  'pgo',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]


PGO_BUILDERS = freeze({
  'chromium.fyi': {
    'Chromium Win PGO Builder': {
      'recipe_config': 'chromium',
      'chromium_config_instrument': 'chromium_pgo_instrument',
      'chromium_config_optimize': 'chromium_pgo_optimize',
      'gclient_config': 'chromium',
      'clobber': True,
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
      },
      'testing': {
        'platform': 'win',
      },
    },
    'Chromium Win x64 PGO Builder': {
      'recipe_config': 'chromium',
      'chromium_config_instrument': 'chromium_pgo_instrument',
      'chromium_config_optimize': 'chromium_pgo_optimize',
      'gclient_config': 'chromium',
      'clobber': True,
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 64,
      },
    },
  },
  'tryserver.chromium.win': {
    'win_pgo': {
      'recipe_config': 'chromium',
      'chromium_config_instrument': 'chromium_pgo_instrument',
      'chromium_config_optimize': 'chromium_pgo_optimize',
      'gclient_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
      },
      'testing': {
        'platform': 'win',
      },
    },
  },
})


def RunSteps(api):
  buildername = api.properties['buildername']
  mainname = api.properties['mainname']
  bot_config = PGO_BUILDERS.get(mainname, {}).get(buildername)

  api.pgo.compile_pgo(bot_config)
  api.archive.zip_and_upload_build(
      'package build',
      api.chromium.c.build_config_fs,
      'gs://chromium-fyi-archive/win_pgo_builds')


def GenTests(api):
  def _sanitize_nonalpha(text):
    return ''.join(c if c.isalnum() else '_' for c in text)

  for mainname, builders in PGO_BUILDERS.iteritems():
    for buildername in builders:
      yield (
        api.test('full_%s_%s' % (_sanitize_nonalpha(mainname),
                                 _sanitize_nonalpha(buildername))) +
        api.properties.generic(mainname=mainname, buildername=buildername) +
        api.platform('win', 64)
      )
