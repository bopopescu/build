# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]

TESTS = [
  {
    'name': 'Test auto-bisect on tester',
    'properties': {
      'workdir': '/b/build/subordinate/linux',
      'repository': 'https://chromium.googlesource.com/v8/v8',
      'buildername': 'V8 Linux - nosnap',
      'parent_buildnumber': 9423,
      'recipe': 'v8',
      'mainname':
      'client.v8',
      'buildbotURL': 'http://build.chromium.org/p/client.v8/',
      'project': 'v8',
      'parent_buildername': 'V8 Linux - nosnap builder',
      'git_revision': 'c08e952566c3923f8fcbd693dae05f8eae73938b',
      'parent_got_revision': 'c08e952566c3923f8fcbd693dae05f8eae73938b',
      'parent_got_swarming_client_revision':
          'df99a00d96fae932bae824dccba13156bf7eddd0',
      'buildnumber': 5472,
      'subordinatename': 'subordinate4-c3',
      'swarm_hashes': {
        'bot_default': '3726ca899b099c077b9551f7163c05ea0f160a7b',
        'mozilla': 'ba5f8a4aeee89b1fe88c764416ee9875584a10d3',
        'simdjs': '55aa4085d018aaf24dc2bc07421515e23cd8a006',
      },
      'blamelist': ['hax@chromium.org', 'dude@chromium.org'],
      'branch': 'main',
      'parent_got_revision_cp': 'refs/heads/main@{#32376}',
      'requestedAt': 1448632553,
      'revision': 'c08e952566c3923f8fcbd693dae05f8eae73938b',
      'override_changes': [
        {'revision': '469675ee3f137970158305957a76615d33ff253c'},
        {'revision': 'd290f204938295bfecc5c8e645ccfcff6e80ddb8'},
        {'revision': 'c08e952566c3923f8fcbd693dae05f8eae73938b'},
      ],
      'bisect_duration_factor': 0.5,
      'testfilter': [
        'cctest/test-serialize/ContextDeserialization',
      ],
    },
    'ok_ret': [1],
    'verifiers': [
      {
        'name': 'verify suspects',
        'regexp': r'Suspecting multiple commits(?:.|\s)*'
                  r'd290f204(?:.|\s)*c08e9525',
      },
    ],
  },
]

def RunSteps(api):
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True)

  for test in TESTS:
    try:
      api.python(
          name=test['name'],
          script=api.path['checkout'].join(
              'scripts', 'tools', 'run_recipe.py'),
          args=[
            'v8',
            '--properties-file',
            api.json.input(test['properties'])
          ],
          ok_ret=test['ok_ret'],
          stdout=api.raw_io.output(),
      )
    finally:
      result = api.step.active_result

      # Make consumed output visible again.
      result.presentation.logs['stdout'] = result.stdout.splitlines()

      # Show return code to ease debugging.
      result.presentation.logs['retcode'] = [str(result.retcode)]

    # Assert invariants.
    for verifier in test['verifiers']:
      if not re.search(verifier['regexp'], result.stdout):
        result.presentation.status = api.step.FAILURE
        result.presentation.logs[verifier['name']] = [
            'Regular expression "%s" did not match.' % verifier['regexp']]
        # Make the overall build fail.
        raise api.step.StepFailure('Verifier did not match.')


def GenTests(api):
  yield (
      api.test('v8-auto-bisect-end-to-end-pass') +
      api.properties.generic(
          mainname='chromium.tools.build',
          buildername='v8-linux-end-to-end',
      ) +
      api.override_step_data(
          'Test auto-bisect on tester',
          api.raw_io.stream_output(
              'Suspecting multiple commits@@\n@@\n@@d290f204@@@\n@@@c08e9525',
              stream='stdout',
          ),
          retcode=1,
      )
  )

  yield (
      api.test('v8-auto-bisect-end-to-end-fail') +
      api.properties.generic(
          mainname='chromium.tools.build',
          buildername='v8-linux-end-to-end',
      ) +
      api.override_step_data(
          'Test auto-bisect on tester',
          api.raw_io.stream_output(
              'Suspecting multiple commits\ndeadbeef\ndeadbeef',
              stream='stdout',
          ),
          retcode=1,
      )
  )
