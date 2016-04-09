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

#
# Linux Rel Builder/Tester
#
# FIXME: Rename this builder to indicate that it is running precise.
B('WebKit Linux', 'f_webkit_linux_rel', scheduler='global_scheduler')
F('f_webkit_linux_rel', m_annotator.BaseFactory('chromium'))

B('WebKit Linux Trusty', 'f_webkit_linux_rel_trusty',
    scheduler='global_scheduler')
F('f_webkit_linux_rel_trusty', m_annotator.BaseFactory('chromium'))

B('WebKit Linux ASAN', 'f_webkit_linux_rel_asan', scheduler='global_scheduler',
    auto_reboot=True)
F('f_webkit_linux_rel_asan', m_annotator.BaseFactory('chromium'))

B('WebKit Linux MSAN', 'f_webkit_linux_rel_msan', scheduler='global_scheduler',
    auto_reboot=True)
F('f_webkit_linux_rel_msan', m_annotator.BaseFactory('chromium'))

B('WebKit Linux Leak', 'f_webkit_linux_leak_rel', scheduler='global_scheduler',
    category='layout')
F('f_webkit_linux_leak_rel', m_annotator.BaseFactory('chromium'))


################################################################################
## Debug
################################################################################

#
# Linux Dbg Webkit builders/testers
#

B('WebKit Linux (dbg)', 'f_webkit_dbg_tests', scheduler='global_scheduler',
    auto_reboot=False)
F('f_webkit_dbg_tests', m_annotator.BaseFactory('chromium'))


def Update(_config, _active_master, c):
  return helper.Update(c)
