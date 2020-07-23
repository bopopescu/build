# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromium',
  'filter',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]

def RunSteps(api):
  test_targets = api.m.properties.get('test_targets')
  additional_compile_targets = api.m.properties.get(
      'additional_compile_targets')

  api.path['checkout'] = api.path['subordinate_build']
  api.chromium.set_config('chromium')
  api.filter.does_patch_require_compile(
      affected_files=list(api.m.properties.get('affected_files', ['foo.cc'])),
      test_targets=test_targets,
      additional_compile_targets=additional_compile_targets,
      additional_names=['chromium'])

  assert (list(api.properties.get('example_changed_paths', ['foo.cc'])) == \
          api.filter.paths)
  assert (list(api.properties.get('example_test_targets', [])) ==
          list(api.filter.test_targets))
  assert (list(api.properties.get('example_compile_targets', [])) ==
          api.filter.compile_targets)
  api.step('hello', ['echo', 'Why hello, there.'])

def GenTests(api):
  # Trivial test with no exclusions and nothing matching.
  yield (api.test('basic') +
         api.properties(
           affected_files=['yy'],
           filter_exclusions=[],
           example_changed_paths=['yy']) +
         api.override_step_data(
          'read filter exclusion spec',
          api.json.output({
           'base': { 'exclusions': [] },
           'chromium': { 'exclusions': [] }})))

  # Matches exclusions
  yield (api.test('match_exclusion') +
         api.properties(affected_files=['foo.cc']) +
         api.override_step_data(
          'read filter exclusion spec',
          api.json.output({
           'base': { 'exclusions': ['fo.*'] },
           'chromium': { 'exclusions': [] }})))

  # Matches exclusions in additional_names key
  yield (api.test('match_additional_name_exclusion') +
         api.properties(affected_files=['foo.cc']) +
         api.override_step_data(
          'read filter exclusion spec',
          api.json.output({
           'base': { 'exclusions': [] },
           'chromium': { 'exclusions': ['fo.*'] }})))

  # Doesnt match exclusion.
  yield (api.test('doesnt_match_exclusion') +
         api.properties(
           affected_files=['bar.cc'],
           example_changed_paths=['bar.cc']) +
         api.override_step_data(
          'read filter exclusion spec',
          api.json.output({
           'base': { 'exclusions': ['fo.*'] },
           'chromium': { 'exclusions': [] }})))

  # Analyze returns matching result.
  yield (api.test('analyzes_returns_true') +
         api.override_step_data(
          'analyze',
          api.json.output({'status': 'Found dependency',
                           'test_targets': [],
                           'compile_targets': []})))

  # Analyze returns matching tests while matching all.
  yield (api.test('analyzes_matches_all_exes') +
         api.override_step_data(
          'analyze',
          api.json.output({'status': 'Found dependency (all)',
                           'test_targets': [],
                           'compile_targets': []})))

  # Analyze matches all and returns matching tests.
  yield (api.test('analyzes_matches_test_targets') +
         api.properties(
           test_targets=['foo', 'bar'],
           example_test_targets=['foo', 'bar'],
           example_compile_targets=['bar', 'foo']) +
         api.override_step_data(
          'analyze',
          api.json.output({'status': 'Found dependency',
                           'test_targets': ['foo', 'bar'],
                           'compile_targets': ['foo', 'bar']})))

  # Analyze matches all and returns matching tests.
  yield (api.test('analyzes_matches_compile_targets') +
         api.properties(
           example_test_targets=['foo'],
           example_compile_targets=['bar', 'foo']) +
         api.override_step_data(
          'analyze',
          api.json.output({'status': 'Found dependency',
                           'test_targets': ['foo'],
                           'compile_targets': ['bar']})))

  # Analyze with error condition.
  yield (api.test('analyzes_error') +
         api.properties(
           test_targets=[]) +
         api.override_step_data(
          'analyze',
          api.json.output({'error': 'ERROR'})))

  # Analyze with python returning bad status.
  yield (api.test('bad_retcode_fails') +
         api.properties(
           test_targets=[]) +
         api.step_data(
          'analyze',
          retcode=-1))

  # invalid_targets creates a failure.
  yield (api.test('invalid_targets') +
         api.properties(
           test_targets=[],
           example_result=1) +
         api.override_step_data(
          'analyze',
          api.json.output({'invalid_targets': ['invalid', 'another one']})))
