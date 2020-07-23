# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import gitiles_poller
from main import main_config
from main import main_utils
from main.factory import annotator_factory

import main_site_config
ActiveMain = main_site_config.ChromiumFYI

defaults = {}

helper = main_config.Helper(defaults)
B = helper.Builder
F = helper.Factory
S = helper.Scheduler

m_annotator = annotator_factory.AnnotatorFactory()

defaults['category'] = 'drmemory'

#
# Main Dr. Memory release scheduler for src/
#
S('chromium_drmemory_lkgr', branch='lkgr')

#
# Windows LKGR DrMemory Builder
#
# crbug.com/399990: short name to avoid hitting path length limit
B('Win LKGR (DrM)', 'win_lkgr_drmemory',
  # not use a gatekeeper yet
  scheduler='chromium_drmemory_lkgr',
  notify_on_missing=True)
F('win_lkgr_drmemory', m_annotator.BaseFactory(recipe='chromium_drfuzz'))

#
# Windows LKGR DrMemory X64 Builder
#
# crbug.com/399990: short name to avoid hitting path length limit
B('Win LKGR (DrM 64)', 'win_lkgr_drmemory_x64',
  # not use a gatekeeper yet
  scheduler='chromium_drmemory_lkgr',
  notify_on_missing=True)
F('win_lkgr_drmemory_x64', m_annotator.BaseFactory(recipe='chromium_drfuzz'))

def Update(_update_config, _active_main, c):
  lkgr_poller = gitiles_poller.GitilesPoller(
    'https://chromium.googlesource.com/chromium/src',
    branches=['lkgr'])
  c['change_source'].append(lkgr_poller)
  return helper.Update(c)
