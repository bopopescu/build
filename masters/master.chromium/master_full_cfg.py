# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from master import master_config
from master.factory import annotator_factory
from master.factory import chromium_factory

import master_site_config

ActiveMaster = master_site_config.Chromium

defaults = {}

helper = master_config.Helper(defaults)
B = helper.Builder
D = helper.Dependent
F = helper.Factory
S = helper.Scheduler
T = helper.Triggerable

def win(): return chromium_factory.ChromiumFactory('src/build', 'win32')
def linux(): return chromium_factory.ChromiumFactory(
    'src/out', 'linux2', pull_internal=False)
def mac(): return chromium_factory.ChromiumFactory('src/xcodebuild', 'darwin')
def linux_android(): return chromium_factory.ChromiumFactory(
    'src/out', 'linux2', nohooks_on_update=True, target_os='android')

m_annotator = annotator_factory.AnnotatorFactory()

defaults['category'] = '1clobber'

# Global scheduler
S('chromium', branch='master', treeStableTimer=60)

################################################################################
## Windows
################################################################################

B('Win', 'win_clobber', 'compile|windows', 'chromium',
  notify_on_missing=True)
F('win_clobber', win().ChromiumFactory(
    clobber=True,
    project='all.sln',
    tests=[
      'check_bins',
      'sizes',
    ],
    options=['--compiler=goma'],
    factory_properties={
      'archive_build': ActiveMaster.is_production_host,
      'confirm_noop_compile': True,
      'gs_bucket': 'gs://chromium-browser-snapshots',
      'gs_acl': 'public-read',
      'show_perf_results': True,
      'perf_id': 'chromium-rel-xp',
      'expectations': True,
      'process_dumps': False,
      'start_crash_handler': True,
      'generate_gtest_json': ActiveMaster.is_production_host,
      'gclient_env': {
        'GYP_DEFINES': 'test_isolation_mode=noop',
        'GYP_USE_SEPARATE_MSPDBSRV': '1',
      },
    }))

################################################################################
## Mac
################################################################################

B('Mac', 'mac_clobber', 'compile|testers', 'chromium',
  notify_on_missing=True)
F('mac_clobber', mac().ChromiumFactory(
    clobber=True,
    tests=[
      'sizes',
    ],
    options=['--compiler=goma-clang'],
    factory_properties={
      'archive_build': ActiveMaster.is_production_host,
      'confirm_noop_compile': True,
      'gs_bucket': 'gs://chromium-browser-snapshots',
      'gs_acl': 'public-read',
      'show_perf_results': True,
      'perf_id': 'chromium-rel-mac',
      'expectations': True,
      'generate_gtest_json': ActiveMaster.is_production_host,
      'gclient_env': {
        'GYP_DEFINES': 'test_isolation_mode=noop mac_strip_release=1',
      },
    }))

################################################################################
## Linux
################################################################################

B('Linux', 'linux_clobber', 'compile|testers', 'chromium',
  notify_on_missing=True)
F('linux_clobber', m_annotator.BaseFactory('chromium'))

B('Linux x64', 'linux64_clobber', 'compile|testers', 'chromium',
  notify_on_missing=True)
F('linux64_clobber', m_annotator.BaseFactory('chromium'))

################################################################################
## Android
################################################################################

B('Android', 'f_android_clobber', None, 'chromium',
  notify_on_missing=True)
F('f_android_clobber', linux_android().ChromiumAnnotationFactory(
    clobber=True,
    target='Release',
    tests=[
      'sizes',
    ],
    factory_properties={
      'android_bot_id': 'main-clobber-rel',
      'archive_build': ActiveMaster.is_production_host,
      'gs_acl': 'public-read',
      'gs_bucket': 'gs://chromium-browser-snapshots',
      'perf_id': 'android-release',
      'show_perf_results': True,
    },
    annotation_script='src/build/android/buildbot/bb_run_bot.py',
    ))


def Update(_config, active_master, c):
  return helper.Update(c)
