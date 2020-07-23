# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main import main_config
from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

defaults = {}

helper = main_config.Helper(defaults)
B = helper.Builder
F = helper.Factory
S = helper.Scheduler
T = helper.Triggerable

defaults['category'] = '5android'

android_dbg_archive = main_config.GetGSUtilUrl(
    'chromium-android', 'android_main_dbg')

android_rel_archive = main_config.GetGSUtilUrl(
    'chromium-android', 'android_main_rel')

#
# Main release scheduler for src/
#
S('android', branch='main', treeStableTimer=60)

#
# Triggerable scheduler for the builder
#
T('android_trigger_dbg')
T('android_trigger_rel')

#
# Android Builder
#
B('Android Arm64 Builder (dbg)', 'f_android_arm64_dbg', 'android', 'android',
  auto_reboot=False, notify_on_missing=True)
F('f_android_arm64_dbg',
  m_annotator.BaseFactory('chromium'))

B('Android Builder (dbg)', 'f_android_dbg', 'android', 'android',
  auto_reboot=False, notify_on_missing=True)
F('f_android_dbg',
  m_annotator.BaseFactory('chromium'))

B('Android Tests (dbg)', 'f_android_dbg_tests', 'android',
  'android_trigger_dbg', notify_on_missing=True)
F('f_android_dbg_tests',
  m_annotator.BaseFactory('chromium'))

B('Android Builder', 'f_android_rel', 'android', 'android',
  notify_on_missing=True)
F('f_android_rel',
  m_annotator.BaseFactory('chromium'))

B('Android Tests', 'f_android_rel_tests', 'android', 'android_trigger_rel',
  notify_on_missing=True)
F('f_android_rel_tests',
  m_annotator.BaseFactory('chromium'))

B('Android Clang Builder (dbg)', 'f_android_clang_dbg', 'android', 'android',
  notify_on_missing=True)
F('f_android_clang_dbg',
  m_annotator.BaseFactory('chromium'))

def Update(_config_arg, _active_main, c):
  helper.Update(c)

  specs = [
    {'name': 'Android GN'},
    {'name': 'Android GN (dbg)'},
    {'name': 'Cast Android (dbg)'},
  ]

  c['schedulers'].extend([
      SingleBranchScheduler(name='android_gn',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[s['name'] for s in specs]),
  ])
  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
              spec.get('recipe', 'chromium'),
              factory_properties=spec.get('factory_properties')),
        'notify_on_missing': True,
        'category': '5android',
      } for spec in specs
  ])
