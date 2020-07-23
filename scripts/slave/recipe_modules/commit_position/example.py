# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

DEPS = [
    'commit_position',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/step',
    ]

VALID_CP = 'refs/heads/main@{#12345}'
INVALID_CP_BAD_FORMAT = 'foo/var@{missing-hash}'
INVALID_CP_NON_NUMERIC = 'refs/heads/main@{#foo}'

def RunSteps(api):
  fake_checkout_path = api.path.mkdtemp('fake_checkout')
  api.path['checkout'] = fake_checkout_path

  # Try to resolve a commit position to a hash
  if 'revision_to_resolve' in api.properties.keys():
    api.commit_position.chromium_hash_from_commit_position(
        api.properties['revision_to_resolve'])

  # Try to resolve a hash to a commit_position
  if 'hash_to_resolve' in api.properties.keys():
    api.commit_position.chromium_commit_position_from_hash(
        api.properties['hash_to_resolve'])

  cp = api.properties['cp']
  expect_revision = api.properties.get('revision')
  expect_branch = api.properties.get('branch')

  # Parse a valid commit position (branch).
  try:
    branch = api.commit_position.parse_branch(cp)
  except ValueError:
    raise recipe_api.StepFailure("Failed to parse branch from: %s" % (cp,))
  api.step('test branch parse', ['/bin/echo', branch])
  assert branch == expect_branch, "Invalid parsed branch: %s" % (branch,)

  # Parse a valid commit position (revision).
  revision = api.commit_position.parse_revision(cp)
  api.step('test revision parse', ['/bin/echo', revision])
  assert revision == expect_revision, "Invalid parsed revision: %s" % (
      revision,)

  # Construct a commit position.
  value = api.commit_position.construct(branch, revision)
  api.step('test construction', ['/bin/echo', value])
  assert value == cp, "Construction failed: %s" % (value,)


def GenTests(api):
  valid_hash = '01234567890abcdef01234567890abcdef01234567'
  yield (
      api.test('valid') +
      api.properties(
        cp=VALID_CP,
        revision=12345,
        branch='refs/heads/main',
        hash_to_resolve=valid_hash) +
      api.step_data('resolving hash ' + valid_hash,
                    stdout=api.raw_io.output(VALID_CP)))

  yield (
      api.test('invalid_bad_format') +
      api.properties(
        cp=INVALID_CP_BAD_FORMAT))

  yield (
      api.test('invalid_non_numeric') +
      api.properties(
        cp=INVALID_CP_NON_NUMERIC))

  yield (
      api.test('invalid_commit_position') +
      api.properties(
        revision_to_resolve='foo'))

  yield (
      api.test('invalid_hash') +
      api.properties(
        hash_to_resolve='foo'))
