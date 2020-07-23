# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from recipe_engine import recipe_api

DEPS = [
    'crrev',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/json',
]


def RunSteps(api):
  if 'commit_position' in api.properties.keys():
    cp = api.properties['commit_position']
    try:
      api.crrev.to_commit_hash(cp)
    except ValueError:
      raise recipe_api.StepFailure('Invalid commit position: %s' % cp)

  if 'commit_hash' in api.properties.keys():
    sha = api.properties['commit_hash']
    try:
      api.crrev.to_commit_position(sha)
    except ValueError:
      raise recipe_api.StepFailure('Invalid commit hash: %s' % sha)


def GenTests(api):
  yield (
      api.test('invalid_commit_position') +
      api.properties(commit_position='foo'))

  yield (
      api.test('invalid_hash') +
      api.properties(commit_hash='foo'))

  yield (
      api.test('valid_hash') +
      api.properties(commit_hash='abcdeabcde0123456789abcdeabcde0123456789') +
      api.step_data(
          name='crrev get commit position for '
               'abcdeabcde0123456789abcdeabcde0123456789',
          stdout=api.json.output({
              'numberings': [
                  {
                      'number': '111',
                      'numbering_identifier': 'refs/heads/main',
                      'numbering_type': 'COMMIT_POSITION',
                  }
              ]})))

  yield (
      api.test('valid_commit_position') +
      api.properties(commit_position='refs/heads/main@{#111}') +
      api.step_data(
          name='crrev get commit hash for refs/heads/main@{#111}',
          stdout=api.json.output({
              'git_sha': 'abcdeabcde0123456789abcdeabcde0123456789'
          })))

  yield (
      api.test('empty_commit_hash_output') +
      api.properties(commit_position='refs/heads/main@{#111}') +
      api.step_data(
          name='crrev get commit hash for refs/heads/main@{#111}',
          stdout=api.json.output({})))

  yield (
      api.test('empty_commit_position_output') +
      api.properties(commit_hash='abcdeabcde0123456789abcdeabcde0123456789') +
      api.step_data(
          name='crrev get commit position for '
               'abcdeabcde0123456789abcdeabcde0123456789',
          stdout=api.json.output({})))

  yield (
      api.test('no_numberings') +
      api.properties(commit_hash='abcdeabcde0123456789abcdeabcde0123456789') +
      api.step_data(
          name='crrev get commit position for '
               'abcdeabcde0123456789abcdeabcde0123456789',
          stdout=api.json.output({'numberings': []})))
