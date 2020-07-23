# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'perf_dashboard',
    'recipe_engine/path',
    'recipe_engine/json',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
]

# To run, pass these options into properties:
# subordinatename="multivm-windows-release",
# buildername="multivm-windows-perf-be",
# mainname="client.dart.fyi", buildnumber=75


def RunSteps(api):
  s1 = api.perf_dashboard.get_skeleton_point('sunspider/string-unpack-code/ref',
                                             33241, '18.5')
  s1['supplemental_columns'] = {'r_webkit_rev': '167808'}
  s1['error'] = '0.5'
  s1['units'] = 'ms'
  s2 = api.perf_dashboard.get_skeleton_point('sunspider/string-unpack-code',
                                             33241, '18.4')
  s2['supplemental_columns'] = {'r_webkit_rev': '167808'}
  s2['error'] = '0.4898'
  s2['units'] = 'ms'

  api.perf_dashboard.set_default_config()
  api.perf_dashboard.post([s1, s2])

  api.perf_dashboard.add_dashboard_link(
      api.step.active_result.presentation,
      'sunspider/string-unpack-code',
      33241,
      bot='bot_name',
  )

  bisect_results = {
      'try_job_id': 1,
      'status': 'completed'
  }
  api.perf_dashboard.post_bisect_results(bisect_results)


def GenTests(api):
  bisect_response = {
      'post_data': {
          'try_job_id': 1,
          'status': 'completed'
      },
      'text': '',
      'status_code': 200
  }
  for platform in ('linux', 'win', 'mac'):
    for production in (True, False):
      yield (api.test('%s%s' %
                      (platform, '_use_mirror'
                       if production else '')) + api.platform.name(platform) +
             api.properties(use_mirror=production,
                            subordinatename='multivm-windows-release',
                            buildername='multivm-windows-perf-be',
                            buildnumber=75,
                            mainname='client.dart.fyi') +
             api.step_data('Post bisect results',
                           stdout=api.json.output(bisect_response)))
