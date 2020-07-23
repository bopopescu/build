# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='win_src',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[
          'Win Builder',
          'Win x64 Builder',
          'Win x64 Builder (dbg)',
          'Win Builder (dbg)',
          'Win x64 GN',
          'Win x64 GN (dbg)',
          'Win8 GN (dbg)',
          'Win8 Aura',
      ]),
  ])
  specs = [
    {'name': 'Win Builder'},
    {'name': 'Win7 (32) Tests'},
    {'name': 'Win7 Tests (1)'},
    {'name': 'Win x64 Builder'},
    {'name': 'Win 7 Tests x64 (1)'},
    {'name': 'Win x64 Builder (dbg)'},
    {'name': 'Win Builder (dbg)'},
    {'name': 'Win7 Tests (dbg)(1)'},
    {'name': 'Win8 Aura'},
    {'name': 'Win x64 GN', 'timeout': 3600},
    {'name': 'Win x64 GN (dbg)'},
    {'name': 'Win8 GN (dbg)'},
    {'name': 'Win10 Tests x64'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            spec.get('recipe', 'chromium'),
            factory_properties=spec.get('factory_properties'),
            timeout=spec.get('timeout', 2400)),
        'notify_on_missing': True,
        'category': '2windows',
      } for spec in specs
  ])
