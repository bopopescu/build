# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def _CheckoutSteps(api):
  api.gclient.set_config('webports')
  result = api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()
  # HACK(aneeshm): Borrowed from iannucci's hack in nacl.py.
  got_revision = result.presentation.properties['got_revision']
  return got_revision

def _AnnotatedStepsSteps(api, got_revision):
  # Default environemnt; required by all builders.
  env = {
      'BUILDBOT_MASTERNAME': api.properties['mainname'],
      'BUILDBOT_BUILDERNAME': api.properties['buildername'],
      'BUILDBOT_REVISION': api.properties['revision'],
      'BUILDBOT_GOT_REVISION': got_revision,
      'BUILDBOT_SLAVE_TYPE': api.properties['subordinatetype'],
  }
  api.step('annotated steps',
      [api.path['checkout'].join('build_tools',
        'buildbot_selector.sh')],
      allow_subannotations=True,
      cwd = api.path['checkout'],
      env = env,
    )


def RunSteps(api):
  got_revision = _CheckoutSteps(api)
  _AnnotatedStepsSteps(api, got_revision)

def GenTests(api):
  yield api.test('linux') +\
    api.platform('linux', 64) +\
    api.properties(mainname = 'client.nacl.ports') +\
    api.properties(buildername = 'linux-glibc-0') +\
    api.properties(revision = 'abcd') +\
    api.properties(subordinatename = 'TestSubordinate') +\
    api.properties(subordinatetype = 'BuilderTester')
