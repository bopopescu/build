#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""changes.ChangeStore unit tests"""

import datetime
import unittest

import test_env  # pylint: disable=W0611

from master.crbuild import common, changes
from master.unittests.deferred_resource_test import run_deferred
from mock import Mock
from twisted.internet import defer


class ChangeStoreTest(unittest.TestCase):
  buildbot = None
  crbuild_change = {
      'id': '1',
      'author': {'email': 'johndoe@chromium.org'},
      'message': 'hello world',
      'revision': 'deadbeef',
      'branch': 'master',
      'create_ts': 1419206400000000,  #  datetime.datetime(2014, 12, 22)
      'project': 'chromium',
      'repo_url': 'http://chromium.googlesource.com/chromium/src',
      'url': 'http://chromium.googlesource.com/chromium/src/+/deadbeef'
  }
  ssid = None

  def setUp(self):
    super(ChangeStoreTest, self).setUp()
    self.buildbot = Mock()
    self.buildbot.change.number = 5
    self.buildbot.get_cache.return_value = self.buildbot.change_cache
    self.buildbot.change_cache.get.return_value = self.buildbot.change

    self.store = changes.ChangeStore(self.buildbot)

  def test_find_change_in_db(self):
    change = Mock()
    rev = 123
    change_id = 'abc'
    change.properties.getProperty.return_value = {'change_id': change_id}
    self.buildbot.get_change_by_id.return_value = change
    self.buildbot.find_changes_by_revision.return_value = [change.changeid]

    result = run_deferred(
        self.store._find_change_in_db((rev, change_id))
    )

    self.assertEqual(result, change)
    change.properties.getProperty.assert_any_call(common.INFO_PROPERTY)
    self.buildbot.find_changes_by_revision.assert_called_once_with(rev)
    self.buildbot.get_change_by_id.assert_called_once_with(change.changeid)

  def test_find_change(self):
    m = Mock()
    change = self.store._find_change(m.revision, m.change_id)
    cache = self.buildbot.change_cache
    cache.get.assert_called_once_with((m.revision, m.change_id))
    self.assertEqual(change, cache.get.return_value)

  def test_get_change(self):
    cache = self.buildbot.change_cache
    cache.get.return_value = None
    result = run_deferred(self.store.get_change(self.crbuild_change))

    info = {
        common.CRBUILD_CHANGE_ID_PROPERTY: '1',
    }
    self.buildbot.add_change_to_db.assert_called_once_with(
        author=self.crbuild_change['author']['email'],
        files=[],
        comments=self.crbuild_change['message'],
        revision=self.crbuild_change['revision'],
        when_timestamp=datetime.datetime(2014, 12, 22),
        branch=self.crbuild_change['branch'],
        category=common.CHANGE_CATEGORY,
        revlink=self.crbuild_change['url'],
        properties={
            common.INFO_PROPERTY: (info, 'Change'),
        },
        repository=self.crbuild_change.get('repo_url'),
        project=self.crbuild_change.get('project'),
    )
    self.assertEqual(result, self.buildbot.get_change_by_id.return_value)

  def test_get_change_with_cached_value(self):
    cache = self.buildbot.change_cache
    result = run_deferred(self.store.get_change(self.crbuild_change))
    self.assertEqual(result, cache.get.return_value)
    self.assertFalse(self.buildbot.add_change_to_db.called)

  def test_get_source_stamp(self):
    result = run_deferred(
        self.store.get_source_stamp([self.crbuild_change]))
    cache = self.buildbot.change_cache
    cache.get.assert_called_once_with(
        (self.crbuild_change['revision'], self.crbuild_change['id']))
    bb_change = cache.get.return_value
    self.buildbot.insert_source_stamp_to_db.assert_called_once_with(
        branch=bb_change.branch,
        revision=bb_change.revision,
        repository=bb_change.repository,
        project=bb_change.project,
        changeids=[bb_change.number],
    )
    self.assertEqual(
        result, self.buildbot.insert_source_stamp_to_db.return_value)

  def test_get_source_stamp_with_cache(self):
    ssid = Mock()
    ss_cache = {
        (self.crbuild_change['id'],): ssid,
    }
    result = run_deferred(
        self.store.get_source_stamp([self.crbuild_change], cache=ss_cache))
    self.assertFalse(self.buildbot.change_cache.get.called)
    self.assertFalse(self.buildbot.insert_source_stamp_to_db.called)
    self.assertEqual(result, ssid)


if __name__ == '__main__':
  unittest.main()
