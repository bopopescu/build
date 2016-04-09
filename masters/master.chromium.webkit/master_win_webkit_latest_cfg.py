# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from master import master_config
from master.factory import annotator_factory

import master_site_config

ActiveMaster = master_site_config.ChromiumWebkit

defaults = {}

helper = master_config.Helper(defaults)
B = helper.Builder
F = helper.Factory
T = helper.Triggerable


m_annotator = annotator_factory.AnnotatorFactory()

defaults['category'] = 'layout'

################################################################################
## Release
################################################################################

# Archive location
rel_archive = master_config.GetGSUtilUrl('chromium-build-transfer',
                                         'WebKit Win Builder')

#
# Triggerable scheduler for testers
#
T('s4_webkit_rel_trigger')

#
# Win Rel Builder
#
B('WebKit Win Builder', 'f_webkit_win_rel',
  scheduler='global_scheduler', builddir='webkit-win-latest-rel',
  auto_reboot=False)
F('f_webkit_win_rel', m_annotator.BaseFactory(
    'chromium', triggers=['s4_webkit_rel_trigger']))

#
# Win Rel WebKit testers
#
B('WebKit Win7', 'f_webkit_rel_tests', scheduler='s4_webkit_rel_trigger')
B('WebKit Win10', 'f_webkit_rel_tests', scheduler='s4_webkit_rel_trigger')
F('f_webkit_rel_tests', m_annotator.BaseFactory('chromium'))

#
# Win x64 Rel Builder (note: currently no x64 testers)
#
B('WebKit Win x64 Builder', 'f_webkit_win_rel_x64',
  scheduler='global_scheduler', builddir='webkit-win-latest-rel-x64',
  auto_reboot=False)
F('f_webkit_win_rel_x64', m_annotator.BaseFactory('chromium'))


################################################################################
## Debug
################################################################################

#
# Triggerable scheduler for testers
#
T('s4_webkit_dbg_trigger')

#
# Win Dbg Builder
#
B('WebKit Win Builder (dbg)', 'f_webkit_win_dbg', scheduler='global_scheduler',
  builddir='webkit-win-latest-dbg', auto_reboot=False)
F('f_webkit_win_dbg', m_annotator.BaseFactory('chromium',
    triggers=['s4_webkit_dbg_trigger']))

#
# Win Dbg WebKit testers
#

B('WebKit Win7 (dbg)', 'f_webkit_dbg_tests',
    scheduler='s4_webkit_dbg_trigger')
F('f_webkit_dbg_tests', m_annotator.BaseFactory('chromium'))

#
# Win x64 Dbg Builder (note: currently no x64 testers)
#
B('WebKit Win x64 Builder (dbg)', 'f_webkit_win_dbg_x64',
  scheduler='global_scheduler', builddir='webkit-win-latest-dbg-x64',
  auto_reboot=False)
F('f_webkit_win_dbg_x64', m_annotator.BaseFactory('chromium'))

def Update(_config, _active_master, c):
  return helper.Update(c)
