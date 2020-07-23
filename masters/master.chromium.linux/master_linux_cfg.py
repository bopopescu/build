# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Triggerable
from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(_config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='linux_src',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[
          'Linux Builder',
          'Linux Builder (dbg)(32)',
          'Linux Builder (dbg)',
          'Cast Linux',
      ]),
  ])
  specs = [
    {'name': 'Linux Builder'},
    {'name': 'Linux Tests'},
    {'name': 'Linux Builder (dbg)(32)'},
    {'name': 'Linux Tests (dbg)(1)(32)'},
    {'name': 'Linux Builder (dbg)'},
    {'name': 'Linux Tests (dbg)(1)'},
    {'name': 'Cast Linux'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            spec.get('recipe', 'chromium'),
            factory_properties=spec.get('factory_properties')),
        'notify_on_missing': True,
        'category': '4linux',
      } for spec in specs
  ])
