# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_mac_scheduler',
                            branch='master',
                            treeStableTimer=0,
                            builderNames=[
                                'Mac64 Debug (parallel)',
                                'Mac64 Release (parallel)',
                                'Mac64 Release (XCode 7)',
                                'Mac64 Release (swarming)',
                                'Mac Asan (parallel)',
                            ]),
  ])

  specs = [
    {
      'name': 'Mac64 Debug (parallel)',
      'slavebuilddir': 'mac64',
    },
    {
      'name': 'Mac64 Release (parallel)',
      'slavebuilddir': 'mac64',
    },
    {
      'name': 'Mac64 Release (XCode 7)',
      'slavebuilddir': 'mac64',
    },
    {
      'name': 'Mac64 Release (swarming)',
      'slavebuilddir': 'mac_swarming',
    },
    {
      'name': 'Mac Asan (parallel)',
      'slavebuilddir': 'mac_asan',
    },
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'mac',
        'slavebuilddir': spec['slavebuilddir'],
      } for spec in specs
  ])
