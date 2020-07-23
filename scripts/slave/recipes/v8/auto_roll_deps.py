# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'url',
]

# Location of the infra-python package's run script.
_RUN_PY = '/opt/infra-python/run.py'

def ContainsChromiumRoll(changes):
  for change in changes:
    if change['subject'].startswith('Update V8 to'):
      return True
  return False

def ExtractStaleRoll(changes, api):
  for change in changes:
    if change['subject'].startswith('Update V8 to'):
      is_in_cq = change['commit']
      if not is_in_cq:
        return change['issue']
  return None

def ResubmitToCQ(issue_id, api):
  api.step(
      'send issue to CQ',
      ['commit_queue', 'set', '-i', issue_id]
  )

def RunSteps(api):
  monitoring_state = 'failure'
  try:
    api.chromium.cleanup_temp()
    api.gclient.set_config('chromium')
    api.gclient.apply_config('v8_bleeding_edge_git')

    step_result = api.python(
        'check roll status',
        api.path['build'].join('scripts', 'tools', 'runit.py'),
        [api.path['build'].join('scripts', 'tools', 'pycurl.py'),
         'https://v8-roll.appspot.com/status'],
        stdout=api.raw_io.output(),
        step_test_data=lambda: api.raw_io.test_api.stream_output(
            '1', stream='stdout')
    )
    step_result.presentation.logs['stdout'] = step_result.stdout.splitlines()
    if step_result.stdout.strip() != '1':
      step_result.presentation.step_text = 'Rolling deactivated'
      monitoring_state = 'deactivated'
      return
    else:
      step_result.presentation.step_text = 'Rolling activated'

    params = {
      'closed': 3,
      'owner': 'v8-autoroll@chromium.org',
      'limit': 30,
      'format': 'json',
    }

    params = api.url.urlencode(params)
    search_url = 'https://codereview.chromium.org/search?' + params

    result = api.url.fetch(
        search_url,
        'check active roll',
        step_test_data=lambda: api.raw_io.test_api.output('{"results": []}')
    )
    results = api.json.loads(result)['results']

    if ContainsChromiumRoll(results):
      stale_roll = ExtractStaleRoll(results, api)

      if stale_roll:
        ResubmitToCQ(stale_roll, api)
        api.step.active_result.presentation.step_text = (
            'Stale roll found. Resubmitted to CQ.')
        monitoring_state = 'stale_roll'
      else:
        api.step.active_result.presentation.step_text = 'Active rolls found.'
        monitoring_state = 'active_roll'

      return

    # Prevent race with gnumbd by waiting.
    api.python.inline(
        'wait for gnumbd',
        'import time; time.sleep(20)',
    )

    api.bot_update.ensure_checkout(force=True, no_shallow=True)

    result = api.python(
        'roll deps',
        api.path['checkout'].join(
            'v8', 'tools', 'release', 'auto_roll.py'),
        ['--chromium', api.path['checkout'],
         '--author', 'v8-autoroll@chromium.org',
         '--reviewer',
         'hablich@chromium.org,machenbach@chromium.org,'
         'yangguo@chromium.org,vogelheim@chromium.org',
         '--roll',
         '--json-output', api.json.output(),
         '--work-dir', api.path['subordinate_build'].join('workdir')],
        cwd=api.path['checkout'].join('v8'),
        step_test_data=lambda: api.json.test_api.output(
            {'monitoring_state': 'success'}),
    )
    monitoring_state = result.json.output['monitoring_state']
  finally:
    counter_config = {
      'name': '/v8/autoroller/count',
      'project': 'v8-roll',
      'result': monitoring_state,
      'value': 1,
    }
    api.python(
        'upload stats',
        _RUN_PY,
        [
          'infra.tools.send_ts_mon_values',
          '--ts-mon-target-type', 'task',
          '--ts-mon-task-service-name', 'auto-roll',
          '--ts-mon-task-job-name', 'roll',
          '--counter', api.json.dumps(counter_config),
        ],
    )


def GenTests(api):
  yield api.test('standard') + api.properties.generic(
      mainname='client.v8.fyi')
  yield (api.test('rolling_deactivated') +
      api.properties.generic(mainname='client.v8') +
      api.override_step_data(
          'check roll status', api.raw_io.stream_output('0', stream='stdout'))
    )
  yield (api.test('active_roll') +
      api.properties.generic(mainname='client.v8') +
      api.override_step_data(
          'check active roll', api.raw_io.output(
              '{"results": [{"subject": "Update V8 to foo",' +
              ' "issue": 123456, "commit": true}]}'))
    )
  yield (api.test('stale_roll') +
      api.properties.generic(mainname='client.v8') +
      api.override_step_data(
          'check active roll', api.raw_io.output(
              '{"results": [{"subject": "Update V8 to foo",' +
              ' "issue": 123456, "commit": false}]}'))
    )

