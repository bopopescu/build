# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(_config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='linux_asan_rel',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[
          'Linux ASan LSan Builder'
      ]),
      Triggerable(name='linux_asan_rel_trigger', builderNames=[
          'Linux ASan LSan Tests (1)',
          'Linux ASan Tests (sandboxed)',
      ]),
  ])
  specs = [
    {
      'name': 'Linux ASan LSan Builder',
      'triggers': ['linux_asan_rel_trigger'],
    },
    {'name': 'Linux ASan LSan Tests (1)'},
    {'name': 'Linux ASan Tests (sandboxed)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            spec.get('recipe', 'chromium'),
            triggers=spec.get('triggers')),
        'notify_on_missing': True,
        'category': '1linux asan lsan',
      } for spec in specs
  ])
