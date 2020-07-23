# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe to test v8/node.js integration."""

from recipe_engine.types import freeze


DEPS = [
  'chromium',
  'depot_tools/gclient',
  'file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
  'v8',
]

BUILDERS = freeze({
  'client.v8.fyi': {
    'builders': {
      'V8 - node.js integration - lkgr': {
        'testing': {
          'platform': 'linux',
        },
      },
    },
  },
})


def _build_and_test(api, suffix=''):
  api.step(
    'configure node.js%s' % suffix,
    [api.path['subordinate_build'].join('node.js', 'configure')],
    cwd=api.path['subordinate_build'].join('node.js'),
  )

  api.step(
    'build and test node.js%s' % suffix,
    ['make', '-j8', 'test'],
    cwd=api.path['subordinate_build'].join('node.js'),
  )


def RunSteps(api):
  v8 = api.v8
  v8.apply_bot_config(BUILDERS)
  api.gclient.apply_config('node_js')
  v8.checkout()
  api.chromium.cleanup_temp()

  try:
    # Build and test the node.js branch as FYI.
    _build_and_test(api, ' - baseline')
  except api.step.StepFailure:  # pragma: no cover
    pass

  # Copy the checked-out v8.
  api.file.rmtree('v8', api.path['subordinate_build'].join('node.js', 'deps', 'v8'))
  api.python(
      name='copy v8 tree',
      script=api.v8.resource('copy_v8.py'),
      args=[
        # Source.
        api.path['subordinate_build'].join('v8'),
        # Destination.
        api.path['subordinate_build'].join('node.js', 'deps', 'v8'),
        # Paths to ignore.
        '.git',
        api.path['subordinate_build'].join('v8', 'buildtools'),
        api.path['subordinate_build'].join('v8', 'out'),
        api.path['subordinate_build'].join('v8', 'third_party'),
      ],
  )

  # Build and test node.js with the checked-out v8.
  _build_and_test(api)


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  for mainname, mainconf in BUILDERS.iteritems():
    for buildername, _ in mainconf['builders'].iteritems():
      yield (
          api.test('_'.join([
            'full',
            _sanitize_nonalpha(mainname),
            _sanitize_nonalpha(buildername),
          ])) +
          api.properties.generic(
              mainname=mainname,
              buildername=buildername,
              branch='refs/heads/lkgr',
              revision='deadbeef',
          )
      )
