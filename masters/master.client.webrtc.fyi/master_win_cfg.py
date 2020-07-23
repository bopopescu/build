# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_windows_scheduler',
                            branch='main',
                            treeStableTimer=0,
                            builderNames=[
                                'Win32 Release (swarming)',
                            ]),
  ])

  specs = [
    {
      'name': 'Win32 Release (swarming)',
      'subordinatebuilddir': 'win_swarming',
    },
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'win',
        'subordinatebuilddir': spec['subordinatebuilddir'],
      } for spec in specs
  ])
