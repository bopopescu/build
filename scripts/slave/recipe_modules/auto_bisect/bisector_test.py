#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import os
import sys
import unittest

root_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir,
    os.path.pardir, os.path.pardir, os.path.pardir))
sys.path.insert(0, os.path.join(root_dir, 'third_party', 'mock-1.0.1'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.path.pardir))

import mock

import auto_bisect.bisector
import auto_bisect.depot_config


class MockRevisionClass(object):  # pragma: no cover

  def __init__(
      self, bisector, commit_hash,
      depot_name='chromium', base_revision=None):
    self.bisector = bisector
    self.commit_hash = commit_hash
    self.depot_name = depot_name
    self.base_revision = base_revision
    self.previous_revision = None
    self.next_revision = None
    self.values = []
    self.overall_return_code = None
    self.deps = {}
    self.status = ''

  def read_deps(self, tester_name):
    pass

  def retest(self):
    self.bisector.last_tested_revision = self
    self.values.append(3)


@mock.patch.object(auto_bisect.bisector.Bisector, 'ensure_sync_main_branch',
                   mock.MagicMock())
class BisectorTest(unittest.TestCase):  # pragma: no cover

  def setUp(self):
    self.bisect_config = {
        'test_type': 'perf',
        'command': ('tools/perf/run_benchmark -v '
                    '--browser=release page_cycler.intl_ar_fa_he'),
        'good_revision': 'abcd5678abcd5678abcd5678abcd5678abcd5678',
        'bad_revision': 'def05678def05678def05678def05678def05678',
        'metric': 'warm_times/page_load_time',
        'repeat_count': '2',
        'max_time_minutes': '5',
        'bug_id': '425582',
        'gs_bucket': 'chrome-perf',
        'builder_host': 'main4.golo.chromium.org',
        'builder_port': '8341',
        'dummy_builds': True,
    }
    self.dummy_api = mock.MagicMock()
    self.dummy_api.internal_bisect = False

  def test_improvement_direction_default(self):
    # By default, no improvement direction should be set
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    self.assertIsNone(bisector.improvement_direction)

  def test_improvement_direction_greater_is_better_fail(self):
    # Improvement up, bad > good: should fail
    self.bisect_config['improvement_direction'] = 1
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.mean_value = 10
    bisector.bad_rev.mean_value = 100
    self.assertFalse(bisector.check_improvement_direction())
    self.assertIn('direction of improvement', ''.join(bisector.warnings))

  def test_improvement_direction_greater_is_better_pass(self):
    # Improvement up, bad < good: should not fail
    self.bisect_config['improvement_direction'] = 1
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.mean_value = 100
    bisector.bad_rev.mean_value = 10
    self.assertTrue(bisector.check_improvement_direction())
    self.assertNotIn('direction of improvement', ''.join(bisector.warnings))

  def test_improvement_direction_lower_is_better_fail(self):
    # Improvement down, bad < good: should fail
    self.bisect_config['improvement_direction'] = -1
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.mean_value = 100
    bisector.bad_rev.mean_value = 10
    self.assertFalse(bisector.check_improvement_direction())
    self.assertIn('direction of improvement', ''.join(bisector.warnings))

  def test_improvement_direction_lower_is_better_pass(self):
    # Improvement down, bad > good: should not fail
    self.bisect_config['improvement_direction'] = -1
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.mean_value = 10
    bisector.bad_rev.mean_value = 100
    self.assertTrue(bisector.check_improvement_direction())
    self.assertNotIn('direction of improvement', ''.join(bisector.warnings))

  def test_improvement_direction_return_code(self):
    # The improvement direction check doesn't apply for return code bisects.
    bisect_config = copy.deepcopy(self.bisect_config)
    bisect_config['test_type'] = 'return_code'
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.mean_value = 1
    bisector.bad_rev.mean_value = 0
    self.assertTrue(bisector.is_return_code_mode())
    self.assertTrue(bisector.check_improvement_direction())

  @mock.patch.object(auto_bisect.bisector.Bisector, 'significantly_different',
                     mock.MagicMock(return_value=True))
  def test_check_initial_confidence_pass(self):
    # patch bisector.significantly_different with true
    # assert both revisions have > 5 samples
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.values = [3, 3, 3, 3, 3, 3]
    bisector.bad_rev.values = [3, 3, 3, 3]
    self.assertTrue(bisector.check_initial_confidence())
    self.assertTrue(len(bisector.bad_rev.values) >= 5)

  @mock.patch.object(auto_bisect.bisector.Bisector, 'significantly_different',
                     mock.MagicMock(return_value=False))
  def test_check_initial_confidence_non_diverging(self):
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, self.bisect_config,
                                             MockRevisionClass)
    bisector.good_rev.values = [3, 3, 3, 3, 3, 3]
    bisector.bad_rev.values = [3, 3, 3, 3]
    self.assertFalse(bisector.check_initial_confidence())
    self.assertTrue(len(bisector.bad_rev.values) >=
                    auto_bisect.bisector.MAX_REQUIRED_SAMPLES or
                    len(bisector.good_rev.values) >=
                    auto_bisect.bisector.MAX_REQUIRED_SAMPLES)

  def test_check_initial_confidence_return_code_pass(self):
    return_code_config = self.bisect_config
    return_code_config['test_type'] = 'return_code'
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, return_code_config,
                                             MockRevisionClass)
    bisector.good_rev.overall_return_code = 0
    bisector.bad_rev.overall_return_code = 1
    self.assertTrue(bisector.check_initial_confidence())

  def test_check_initial_confidence_return_code_fail(self):
    return_code_config = self.bisect_config
    return_code_config['test_type'] = 'return_code'
    bisector = auto_bisect.bisector.Bisector(self.dummy_api, return_code_config,
                                             MockRevisionClass)
    bisector.good_rev.overall_return_code = 0
    bisector.bad_rev.overall_return_code = 0
    self.assertFalse(bisector.check_initial_confidence())

    bisector.good_rev.overall_return_code = 1
    bisector.bad_rev.overall_return_code = 1
    self.assertFalse(bisector.check_initial_confidence())

  def test_commit_log_from_gitiles(self):
    self.dummy_api.internal_bisect = True
    commits = [
        {'commit': 'def05678def05678def05678def05678def05678'},  # bad revision
        {'commit': 'bbbbb'},
        {'commit': 'ccccc'},
    ]
    self.dummy_api.m.gitiles.log = mock.MagicMock(return_value=(commits, None))
    auto_bisect.depot_config.DEPOT_DEPS_NAME['android-chrome'] = {
        'src' : 'src/internal',
        'recurse' : True,
        'depends' : None,
        'from' : [],
        'deps_file': '.DEPS.git',
        'url': 'https://dummy-internal-url'
    }
    bisector = auto_bisect.bisector.Bisector(
        self.dummy_api, self.bisect_config, MockRevisionClass)
    for r in bisector.revisions:
      self.assertIn(r.commit_hash,
                    [bisector.good_rev.commit_hash,
                     'bbbbb',
                     'ccccc',
                     bisector.bad_rev.commit_hash])

if __name__ == '__main__':
  unittest.main()  # pragma: no cover
