# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(config, active_master, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='win_src',
                            branch='master',
                            treeStableTimer=60,
                            builderNames=[
          'Win Builder',
          'Win x64 Builder',
          'Win x64 Builder (dbg)',
          'Win Builder (dbg)',
      ]),
      Triggerable(name='win_rel_trigger', builderNames=[
          'XP Tests (1)',
          'Vista Tests (1)',
          'Vista Tests (2)',
          'Vista Tests (3)',
          'Win7 Tests (1)',
          'NaCl Tests (x86-32)',
          'NaCl Tests (x86-64)',
      ]),
      Triggerable(name='win_x64_rel_trigger', builderNames=[
          'Win 7 Tests x64 (1)',
      ]),
      Triggerable(name='win_dbg_trigger', builderNames=[
          'Win7 Tests (dbg)(1)',
          'Win8 Aura',
      ]),
  ])
  specs = [
    {
      'name': 'Win Builder',
      'triggers': ['win_rel_trigger'],
    },
    {'name': 'XP Tests (1)'},
    {'name': 'Vista Tests (1)'},
    {'name': 'Vista Tests (2)'},
    {'name': 'Vista Tests (3)'},
    {'name': 'Win7 Tests (1)'},
    {
      'name': 'Win x64 Builder',
      'triggers': ['win_x64_rel_trigger'],
    },
    {'name': 'Win 7 Tests x64 (1)'},
    {'name': 'NaCl Tests (x86-32)'},
    {'name': 'NaCl Tests (x86-64)'},
    {'name': 'Win x64 Builder (dbg)'},
    {
      'name': 'Win Builder (dbg)',
      'triggers': ['win_dbg_trigger'],
    },
    {'name': 'Win7 Tests (dbg)(1)'},
    {'name': 'Win8 Aura'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            'chromium',
            factory_properties=spec.get('factory_properties'),
            triggers=spec.get('triggers'),
            timeout=spec.get('timeout', 2400)),
        'notify_on_missing': True,
        'category': '2windows',
      } for spec in specs
  ])
