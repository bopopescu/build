# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from main import main_config
from main.factory import annotator_factory

import main_site_config

ActiveMain = main_site_config.ChromiumWebkit

defaults = {}

helper = main_config.Helper(defaults)
B = helper.Builder
F = helper.Factory
T = helper.Triggerable

m_annotator = annotator_factory.AnnotatorFactory()


################################################################################
## Release
################################################################################

defaults['category'] = 'layout'

#
# Triggerable scheduler for the builder
#
T('android_rel_trigger')

#
# Android Rel Builder
#
B('Android Builder', 'f_android_rel', scheduler='global_scheduler')
F('f_android_rel', m_annotator.BaseFactory(
    'chromium', triggers=['android_rel_trigger']))

B('WebKit Android (Nexus4)', 'f_webkit_android_tests', None,
  'android_rel_trigger')
F('f_webkit_android_tests', m_annotator.BaseFactory('chromium'))

def Update(_config, _active_main, c):
  return helper.Update(c)
