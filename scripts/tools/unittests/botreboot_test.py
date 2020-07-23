#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import test_env  # pylint: disable=W0611
from common import find_depot_tools  # pylint: disable=W0611

import os
import subprocess
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(CURR_DIR, os.pardir, os.pardir)
BUILD_DIR = os.path.join(SCRIPTS_DIR, os.pardir)
SITE_CONFIG_DIR = os.path.join(BUILD_DIR, 'site_config')
DEPOT_TOOLS_DIR = os.path.join(BUILD_DIR, os.pardir, 'depot_tools')

sys.path.insert(0, SITE_CONFIG_DIR)
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, DEPOT_TOOLS_DIR)

# Trick reboot_tools to accept a dummy main config
import config_bootstrap
import subordinate.reboot_tools
from testing_support import auto_stub


class DummyMainReboot(config_bootstrap.Main.Main1):
  project_name = 'Dummy Main Reboot'
  reboot_on_step_timeout = True


class DummyMainNoReboot(config_bootstrap.Main.Main1):
  project_name = 'Dummy Main No Reboot'
  reboot_on_step_timeout = False

class DummyMainDefault(config_bootstrap.Main.Main1):
  project_name = 'Dummy Main Default'

class SleepException(Exception):
  pass


def MockSleep(desired_sleep):
  raise SleepException


class BotRebootTest(auto_stub.TestCase):

  def setUp(self):
    super(BotRebootTest, self).setUp()
    self.log_messages = []
    self.subprocess_calls = []
    if hasattr(os.environ, 'TESTING_MASTER'):
      del os.environ['TESTING_MASTER']
    self.mock(subordinate.reboot_tools, 'Log', self.MockLog)
    self.mock(subprocess, 'call', self.MockCall)
    self.mock(subordinate.reboot_tools, 'Sleep', MockSleep)

  def tearDown(self):
    if hasattr(os.environ, 'TESTING_MASTER'):
      del os.environ['TESTING_MASTER']
    super(BotRebootTest, self).tearDown()

  def MockLog(self, msg):
    self.log_messages.append(msg)

  def MockCall(self, args):
    self.subprocess_calls.append(args)

  def test_reboot(self):
    setattr(config_bootstrap.Main, 'active_main', DummyMainReboot)
    # Run in test mode, don't actually reboot
    os.environ['TESTING_MASTER'] = 'DummyMainReboot'
    subordinate.reboot_tools.Reboot()
    msg = 'Reboot: Testing mode enabled, skipping the actual reboot'
    self.assertIn(msg, self.log_messages)

  def test_no_record(self):
    setattr(config_bootstrap.Main, 'active_main', DummyMainDefault)
    # Run in test mode, don't actually reboot
    os.environ['TESTING_MASTER'] = 'DummyMainDefault'
    subordinate.reboot_tools.Reboot()
    msg = 'Reboot: Testing mode enabled, skipping the actual reboot'
    self.assertIn(msg, self.log_messages)

  def test_no_reboot(self):
    setattr(config_bootstrap.Main, 'active_main', DummyMainNoReboot)
    # Run in test mode, don't actually reboot
    os.environ['TESTING_MASTER'] = 'DummyMainNoReboot'
    subordinate.reboot_tools.Reboot()
    msg = 'Reboot: Testing mode enabled, skipping the actual reboot'
    self.assertNotIn(msg, self.log_messages)
    self.assertNotIn('Reboot: Issuing Reboot...', self.log_messages)

  def test_issue_reboot(self):
    setattr(config_bootstrap.Main, 'active_main', DummyMainReboot)
    # Do NOT define TESTING_MASTER, we want to reach IssueReboot().
    # However, setup a backdoor to capture the shutdown command and
    # provide a quick exit from the infinite loop
    try:
      subordinate.reboot_tools.Reboot()
    except SleepException:
      pass
    calls_expected = [['sudo', 'shutdown', '-r', 'now']]
    self.assertIn('Reboot: Issuing Reboot...', self.log_messages)
    self.assertEqual(calls_expected, self.subprocess_calls)


if __name__ == '__main__':
  unittest.TestCase.maxDiff = None
  unittest.main()
