# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'webrtc',
]


def RunSteps(api):
  api.gclient.set_config('webrtc')

  step_result = api.python(
        'check roll status',
        api.path['build'].join('scripts', 'tools', 'pycurl.py'),
        args=['https://webrtc-roll-cr-rev-status.appspot.com/status'],
        stdout=api.raw_io.output(),
        step_test_data=lambda: api.raw_io.test_api.stream_output(
            '1', stream='stdout')
  )
  step_result.presentation.logs['stdout'] = step_result.stdout.splitlines()
  if step_result.stdout.strip() != '1':
    step_result.presentation.step_text = 'Rolling deactivated'
    return
  else:
    step_result.presentation.step_text = 'Rolling activated'

  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  # Enforce a clean state.
  api.git(
      'checkout', '-f', 'main',
      cwd=api.path['checkout'],
  )
  api.git(
      'clean', '-ffd',
      cwd=api.path['checkout'],
  )

  # Run the roll script. It will take care of branch creation, modifying DEPS,
  # uploading etc. It will also delete any previous roll branch.
  api.python(
      'autoroll chromium_revision',
      api.path['checkout'].join('tools', 'autoroller',
                                'roll_chromium_revision.py'),
      ['--clean', '--verbose'],
      cwd=api.path['checkout'],
  )


def GenTests(api):
  yield (
      api.test('rolling_activated') +
      api.properties.generic(mainname='client.webrtc.fyi',
                             buildername='Auto-roll - WebRTC DEPS')
  )
  yield (api.test('rolling_deactivated') +
      api.properties.generic(mainname='client.webrtc.fyi',
                             buildername='Auto-roll - WebRTC DEPS') +
      api.override_step_data('check roll status',
                             api.raw_io.stream_output('0', stream='stdout'))
  )
