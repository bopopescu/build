# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_linux_scheduler',
                            branch='master',
                            treeStableTimer=0,
                            builderNames=[
                                'Linux64 Release (swarming)',
                                'Linux Tsan v2 (parallel)',
      ]),
  ])

  specs = [
    {
      'name': 'Linux Tsan v2 (parallel)',
      'slavebuilddir': 'linux_tsan2',
    },
    {
      'name': 'Linux64 Release (swarming)',
      'slavebuilddir': 'linux_swarming',
    },
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'linux',
        'slavebuilddir': spec['slavebuilddir'],
        'auto_reboot': False,
      } for spec in specs
  ])
