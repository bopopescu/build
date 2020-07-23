#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Source file for main_utils testcases."""


import unittest

import test_env  # pylint: disable=W0611,W0403

from buildbot.process.properties import Properties
from main import main_utils


class MainUtilsTest(unittest.TestCase):

  def testPartition(self):
    partitions = main_utils.Partition([(1, 'a'),
                                         (2, 'b'),
                                         (3, 'c'),
                                         ], 2)
    self.assertEquals([['a', 'b'], ['c']], partitions)


class MockBuilder(object):
  def __init__(self, name):
    self.name = name

class MockSubordinate(object):
  def __init__(self, name, properties):
    self.properties = Properties()
    self.properties.update(properties, "BuildSubordinate")
    self.properties.setProperty("subordinatename", name, "BuildSubordinate")

class MockSubordinateBuilder(object):
  def __init__(self, name, properties):
    self.name = name
    self.subordinate = MockSubordinate(name, properties)

class PreferredBuilderNextSubordinateFuncTest(unittest.TestCase):
  def testNextSubordinate(self):
    builder1 = MockBuilder('builder1')
    builder2 = MockBuilder('builder2')
    builder3 = MockBuilder('builder3')

    subordinates = [
        MockSubordinateBuilder('subordinate1', {'preferred_builder': 'builder1'}),
        MockSubordinateBuilder('subordinate2', {'preferred_builder': 'builder2'}),
        MockSubordinateBuilder('subordinate3', {'preferred_builder': 'builder3'}),
    ]

    f = main_utils.PreferredBuilderNextSubordinateFunc()
    self.assertEqual('subordinate1', f(builder1, subordinates).name)
    self.assertEqual('subordinate2', f(builder2, subordinates).name)
    self.assertEqual('subordinate3', f(builder3, subordinates).name)

    # Remove subordinate 3.
    del subordinates[2]

    # When there is no subordinate that matches preferred_builder,
    # any subordinate builder might be chosen.
    self.assertTrue(f(builder3, subordinates).name in ['subordinate1', 'subordinate2'])

  def testNextSubordinateEmpty(self):
    builder = MockBuilder('builder')
    subordinates = []

    f = main_utils.PreferredBuilderNextSubordinateFunc()

    self.assertIsNone(f(builder, subordinates))


if __name__ == '__main__':
  unittest.main()
