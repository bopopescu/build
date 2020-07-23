# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(_config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='mac_asan_rel',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[
          'Mac ASan 64 Builder',
      ]),
      Triggerable(name='mac_asan_64_rel_trigger', builderNames=[
          'Mac ASan 64 Tests (1)',
      ]),
  ])
  specs = [
    {
      'name': 'Mac ASan 64 Builder',
      'triggers': ['mac_asan_64_rel_trigger'],
    },
    {'name': 'Mac ASan 64 Tests (1)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            spec.get('recipe', 'chromium'),
            triggers=spec.get('triggers')),
        'notify_on_missing': True,
        'category': '2mac asan',
      } for spec in specs
  ])

