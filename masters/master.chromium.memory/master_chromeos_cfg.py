# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(_config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(
          name='chromeos_asan_rel',
          branch='main',
          treeStableTimer=60,
          builderNames=['Linux Chromium OS ASan LSan Builder']),
      Triggerable(
          name='chromeos_asan_rel_trigger',
          builderNames=['Linux Chromium OS ASan LSan Tests (1)']),
  ])

  specs = [
    {
      'name': 'Linux Chromium OS ASan LSan Builder',
      'triggers': ['chromeos_asan_rel_trigger']
    },
    {'name': 'Linux Chromium OS ASan LSan Tests (1)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('chromium',
                                           triggers=spec.get('triggers')),
        'notify_on_missing': True,
        'category': '3chromeos asan',
      } for spec in specs
  ])
