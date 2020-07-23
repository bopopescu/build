# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import collections
import json

DEPS = [
    'auto_bisect',
    'recipe_engine/properties',
    'test_utils',
    'chromium_tests',
    'recipe_engine/raw_io',
    'recipe_engine/step',
    'halt',
    'recipe_engine/json',
]

def RunSteps(api):
  mainname = api.m.properties.get('mainname')
  buildername = api.m.properties.get('buildername')
  # TODO(akuegel): Explicitly load the configs for the builders and don't rely
  # on builders.py in chromium_tests recipe module.
  bot_config = api.chromium_tests.create_bot_config_object(
      mainname, buildername)
  api.chromium_tests.configure_build(bot_config)
  api.m.chromium_tests.prepare_checkout(bot_config)
  api.auto_bisect.perform_bisect()

def GenTests(api):
  basic_test = api.test('basic')
  broken_bad_rev_test = api.test('broken_bad_revision_test')
  broken_good_rev_test = api.test('broken_good_revision_test')
  return_code_test = api.test('basic_return_code_test')
  basic_test += api.properties.generic(
      mainname='tryserver.chromium.perf',
      buildername='linux_perf_bisector')
  broken_bad_rev_test += api.properties.generic(
      mainname='tryserver.chromium.perf',
      buildername='linux_perf_bisector')
  broken_good_rev_test += api.properties.generic(
      mainname='tryserver.chromium.perf',
      buildername='linux_perf_bisector')
  return_code_test += api.properties.generic(
      mainname='tryserver.chromium.perf',
      buildername='linux_perf_bisector')

  bisect_config = {
      'test_type': 'perf',
      'command': ('tools/perf/run_benchmark -v '
                  '--browser=release page_cycler.intl_ar_fa_he'),
      'good_revision': '306475',
      'bad_revision': '306478',
      'metric': 'warm_times/page_load_time',
      'repeat_count': '2',
      'max_time_minutes': '5',
      'bug_id': '425582',
      'gs_bucket': 'chrome-perf',
      'builder_host': 'main4.golo.chromium.org',
      'builder_port': '8341',
      'dummy_initial_confidence': '95',
      'poll_sleep': 0,
      'dummy_builds': True,
      'dummy_job_names': True,
      'bypass_stats_check': True,
  }
  invalid_cp_bisect_config = dict(bisect_config)
  invalid_cp_bisect_config['good_revision'] = 'XXX'

  basic_test += api.properties(bisect_config=bisect_config)
  broken_bad_rev_test += api.properties(bisect_config=bisect_config)
  broken_good_rev_test += api.properties(bisect_config=bisect_config)

  # This data represents fake results for a basic scenario, the items in it are
  # passed to the `_gen_step_data_for_revision` that patches the necessary steps
  # with step_data instances.
  def test_data():
    return [
        {
            'refrange': True,
            'hash': 'a6298e4afedbf2cd461755ea6f45b0ad64222222',
            'commit_pos': '306478',
            'test_results': {
                'results': {
                    'mean': 20,
                    'std_err': 1,
                    'values': [19, 20, 21],
                },
                'retcodes':[0],
            },
            'cl_info': {
                'author': 'DummyAuthor',
                'email': 'dummy@nowhere.com',
                'subject': 'Some random CL',
                'date': '01/01/2015',
                'body': ('A long description for a CL.\n'
                         'Containing multiple lines'),
            },
        },
        {
            'hash': '00316c9ddfb9d7b4e1ed2fff9fe6d964d2111111',
            'commit_pos': '306477',
            'test_results': {
                'results': {
                    'mean': 15,
                    'std_err': 1,
                    'values': [14, 15, 16],
                },
                'retcodes':[0],
            }
        },
        {
            'hash': 'fc6dfc7ff5b1073408499478969261b826441144',
            'commit_pos': '306476',
            'test_results': {
                'results': {
                    'mean': 70,
                    'std_err': 2,
                    'values': [68, 70, 72],
                },
                'retcodes':[0],
            }
        },
        {
            'refrange': True,
            'hash': 'e28dc0d49c331def2a3bbf3ddd0096eb51551155',
            'commit_pos': '306475',
            'test_results': {
                'results': {
                    'mean': 80,
                    'std_err': 10,
                    'values': [70, 70, 80, 90, 90],
                },
                'retcodes':[0],
            }
        },
    ]

  basic_test_data = test_data()
  for revision_data in basic_test_data:
    for step_data in _get_step_data_for_revision(api, revision_data):
      basic_test += step_data
  basic_test += _get_revision_range_step_data(api, basic_test_data)
  basic_test += _get_post_bisect_step_data(api)
  yield basic_test

  broken_test_data = test_data()
  broken_test_data[0].pop('cl_info')

  doctored_data = test_data()
  doctored_data[0]['test_results']['results']['errors'] = ['Dummy error.']
  for revision_data in doctored_data:
    revision_data.pop('cl_info', None)
    skip_results = revision_data in doctored_data[1:-1]
    for step_data in _get_step_data_for_revision(api, revision_data,
                                                 skip_results=skip_results):
      broken_bad_rev_test += step_data
  broken_bad_rev_test += _get_revision_range_step_data(api, doctored_data)
  broken_bad_rev_test += _get_post_bisect_step_data(api)
  yield broken_bad_rev_test

  doctored_data = test_data()
  doctored_data[-1]['test_results']['results']['errors'] = ['Dummy error.']
  for revision_data in doctored_data:
    revision_data.pop('cl_info', None)
    skip_results = revision_data in doctored_data[1:-1]
    for step_data in _get_step_data_for_revision(api, revision_data,
                                                 skip_results=skip_results):
      broken_good_rev_test += step_data
  broken_good_rev_test += _get_revision_range_step_data(api, doctored_data)
  broken_good_rev_test += _get_post_bisect_step_data(api)
  yield broken_good_rev_test

  def return_code_test_data():
    return [
        {
            'refrange': True,
            'hash': 'a6298e4afedbf2cd461755ea6f45b0ad64222222',
            'commit_pos': '306478',
            'test_results': {
                'results': {
                    'mean': 1,
                    'std_err': 0,
                    'values': [],
                },
                'retcodes':[1],
            },
            'cl_info': {
                'author': 'DummyAuthor',
                'email': 'dummy@nowhere.com',
                'subject': 'Some random CL',
                'date': '01/01/2015',
                'body': ('A long description for a CL.\n'
                         'Containing multiple lines'),
            },
        },
        {
            'hash': '00316c9ddfb9d7b4e1ed2fff9fe6d964d2111111',
            'commit_pos': '306477',
            'test_results': {
                'results': {
                    'mean': 1,
                    'std_err': 0,
                    'values': [],
                },
                'retcodes':[1],
            }
        },
        {
            'hash': 'fc6dfc7ff5b1073408499478969261b826441144',
            'commit_pos': '306476',
            'test_results': {
                'results': {
                    'mean': 1,
                    'std_err': 0,
                    'values': [],
                },
                'retcodes':[1],
            }
        },
        {
            'refrange': True,
            'hash': 'e28dc0d49c331def2a3bbf3ddd0096eb51551155',
            'commit_pos': '306475',
            'test_results': {
                'results': {
                    'mean': 0,
                    'std_err': 0,
                    'values': [],
                },
                'retcodes':[0],
            }
        },
    ]

  bisect_config_ret_code = bisect_config.copy()
  bisect_config_ret_code['test_type'] = 'return_code'
  return_code_test += api.properties(bisect_config=bisect_config_ret_code)
  return_code_test_data = return_code_test_data()
  for revision_data in return_code_test_data:
    for step_data in _get_step_data_for_revision(api, revision_data):
      return_code_test += step_data
  return_code_test += _get_revision_range_step_data(api, return_code_test_data)
  return_code_test += _get_post_bisect_step_data(api)
  yield return_code_test


def _get_revision_range_step_data(api, range_data):
  """Gives canned output for fetch_intervening_revisions.py."""
  range_data.sort(key=lambda r: r['commit_pos'])
  min_rev = range_data[0]['hash']
  max_rev = range_data[-1]['hash']
  output = [[r['hash'], 'ignored'] for r in range_data[1:-1]]
  step_name = ('Expanding revision range.for revisions %s:%s' %
               (min_rev, max_rev))
  return api.step_data(step_name, stdout=api.json.output(output))


def _get_step_data_for_revision(api, revision_data, skip_results=False):
  """Generator that produces step patches for fake results."""
  commit_pos_number = revision_data['commit_pos']
  commit_hash = revision_data['hash']
  test_results = revision_data['test_results']

  if 'refrange' in revision_data:
    parent_step = 'Resolving reference range.'
    commit_pos = 'refs/heads/main@{#%s}' % commit_pos_number
    step_name = parent_step + 'crrev get commit hash for ' + commit_pos
    yield api.step_data(
        step_name,
        stdout=api.json.output({'git_sha': commit_hash}))

  if not skip_results:
    step_name = ('Waiting for chromium@%s.gsutil '
                 'Get test results for build %s') % (commit_hash[:10],
                                                     commit_hash)
    if 'refrange' in revision_data:
      parent_step = 'Gathering reference values.'
    else:
      parent_step = 'Working on revision %s.' % ('chromium@' + commit_hash[:10])
      yield _get_post_bisect_step_data(api, parent_step)
    step_name = parent_step + step_name
    yield api.step_data(step_name, stdout=api.raw_io.output(json.dumps(
        test_results)))

    if 'cl_info' in revision_data:
      step_name = 'Reading culprit cl information.'
      stdout = api.json.output(revision_data['cl_info'])
      yield api.step_data(step_name, stdout=stdout)


def _get_post_bisect_step_data(api, parent_step=''):
  """Gets step data for perf_dashboard/resource/post_json.py."""
  response = {'status_code': 200}
  return api.step_data(parent_step + 'Post bisect results',
                       stdout=api.json.output(response))
