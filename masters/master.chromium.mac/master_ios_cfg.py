# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(config, active_main, c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='ios',
                            branch='main',
                            treeStableTimer=60,
                            builderNames=[
          'iOS_Device',
          'iOS_Simulator_(dbg)',
          'iOS_Device_(ninja)',
          'iOS_Device_GN',
          'iOS_Simulator_GN_(dbg)',
      ]),
  ])
  specs = [
    {'name': 'iOS_Device'},
    {'name': 'iOS_Simulator_(dbg)'},
    {'name': 'iOS_Device_(ninja)'},
    {'name': 'iOS_Device_GN'},
    {'name': 'iOS_Simulator_GN_(dbg)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(
            'ios/unified_builder_tester',
            factory_properties=spec.get('factory_properties')),
        'notify_on_missing': True,
        'category': '3mac',
      } for spec in specs
  ])
