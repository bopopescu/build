# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'json',
  'step',
]


def GenSteps(api):
  step_result = api.step('echo', ['echo', '[1, 2, 3]'],
      stdout=api.json.output())
  assert step_result.stdout == [1, 2, 3]

  assert api.json.is_serializable('foo')
  assert not api.json.is_serializable(set(['foo', 'bar', 'baz']))


def GenTests(api):
  yield (api.test('basic') +
      api.step_data('echo', stdout=api.json.output([1, 2, 3])))
