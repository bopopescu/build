#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for scripts/tools/mainmap.py"""


import json
import unittest

import test_env  # pylint: disable=W0611

from tools import mainmap


class FakeOutput(object):
  def __init__(self):
    self.spec = None
    self.data = None

  def __call__(self, spec, data):
    self.spec = spec
    self.data = data


class FakeOpts(object):
  verbose = None
  full_host_names = False


class HelperTest(unittest.TestCase):

  def test_getint_succeeds(self):
    res = mainmap.getint('10')
    self.assertEquals(res, 10)

  def test_getint_fails(self):
    res = mainmap.getint('foo')
    self.assertEquals(res, 0)

  def test_format_host_name_chromium(self):
    res = mainmap.format_host_name('main1.golo.chromium.org')
    self.assertEquals(res, 'main1.golo')

  def test_format_host_name_corp(self):
    res = mainmap.format_host_name('main.chrome.corp.google.com')
    self.assertEquals(res, 'main.chrome')

  def test_format_host_name_neither(self):
    res = mainmap.format_host_name('mymachine.tld')
    self.assertEquals(res, 'mymachine.tld')


class MapTest(unittest.TestCase):

  def test_column_names(self):
    output = FakeOutput()
    mainmap.main_map([], output, FakeOpts())
    self.assertEqual([ s[0] for s in output.spec ],
        ['Main', 'Config Dir', 'Host', 'Web port', 'Subordinate port',
          'Alt port', 'URL'])

  def test_exact_output(self):
    output = FakeOutput()
    main = {
      'name': 'Chromium',
      'dirname': 'main.chromium',
      'host': 'main1.golo',
      'fullhost': 'main1.golo.chromium.org',
      'port': 30101,
      'subordinate_port': 40101,
      'alt_port': 50101,
      'buildbot_url': 'https://build.chromium.org/p/chromium',
    }
    mainmap.main_map([main], output, FakeOpts())
    self.assertEqual(output.data, [ main ])


class FindPortTest(unittest.TestCase):

  @staticmethod
  def _gen_mains(num):
    return [{
        'name': 'Main%d' % i,
        'dirname': 'main.main%d' % i,
        'host': 'main%d.golo' % i,
        'fullhost': 'main%d.golo.chromium.org' % i,
        'port': 20100 + i,
        'subordinate_port': 30100 + i,
        'alt_port': 40100 + i,
    } for i in xrange(num)]

  def test_main_host(self):
    mains = self._gen_mains(2)
    output = FakeOutput()
    mainmap.find_port('Main1', mains, output, FakeOpts())
    self.assertEquals(output.data[0]['main_base_class'], 'Main1')

  def test_skip_used_ports(self):
    mains = self._gen_mains(5)
    main_class_name = 'Main1'
    output = FakeOutput()
    mainmap.find_port(main_class_name, mains, output, FakeOpts())
    self.assertEquals(output.data, [ {
        u'main_base_class': u'Main1',
        u'main_port': u'20105',
        u'main_port_alt': u'25105',
        u'subordinate_port': u'30105',
    } ])

  def test_skip_blacklisted_ports(self):
    mains = [{'name': 'Main1', 'fullhost': 'main1.golo.chromium.org'}]
    main_class_name = 'Main1'
    output = FakeOutput()
    _real_blacklist = mainmap.PORT_BLACKLIST
    try:
      mainmap.PORT_BLACKLIST = set(xrange(25000, 30000))  # All alt_ports
      self.assertRaises(RuntimeError, mainmap.find_port,
                        main_class_name, mains, output, FakeOpts())
    finally:
      mainmap.PORT_BLACKLIST = _real_blacklist


class AuditTest(unittest.TestCase):
  # TODO(agable): Actually test this.
  pass


if __name__ == '__main__':
  unittest.TestCase.maxDiff = None
  unittest.main()
