# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import main_config
from main.factory import annotator_factory

import main_site_config

ActiveMain = main_site_config.Chromium

defaults = {}

helper = main_config.Helper(defaults)
B = helper.Builder
D = helper.Dependent
F = helper.Factory
S = helper.Scheduler
T = helper.Triggerable

m_annotator = annotator_factory.AnnotatorFactory()

defaults['category'] = '1clobber'

# Global scheduler
S('chromium', branch='main', treeStableTimer=60)

################################################################################
## Windows
################################################################################

B('Win', 'win_clobber', 'compile|windows', 'chromium',
  notify_on_missing=True)
F('win_clobber', m_annotator.BaseFactory('chromium'))

################################################################################
## Mac
################################################################################

B('Mac', 'mac_clobber', 'compile|testers', 'chromium',
  notify_on_missing=True)
F('mac_clobber', m_annotator.BaseFactory('chromium'))

################################################################################
## Linux
################################################################################

B('Linux x64', 'linux64_clobber', 'compile|testers', 'chromium',
  notify_on_missing=True)
F('linux64_clobber', m_annotator.BaseFactory('chromium'))

################################################################################
## Android
################################################################################

B('Android', 'f_android_clobber', None, 'chromium',
  notify_on_missing=True)
F('f_android_clobber', m_annotator.BaseFactory('chromium'))


def Update(_config, active_main, c):
  return helper.Update(c)
