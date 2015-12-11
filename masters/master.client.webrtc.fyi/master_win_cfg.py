# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_windows_scheduler',
                            branch='master',
                            treeStableTimer=0,
                            builderNames=[
                                'Win32 Release (swarming)',
                                'Win32 Debug (Clang)',
                                'Win32 Release (Clang)',
                                'Win64 Debug (Clang)',
                                'Win64 Release (Clang)',
                            ]),
  ])

  specs = [
    {
      'name': 'Win32 Release (swarming)',
      'slavebuilddir': 'win_swarming',
    },
    {'name': 'Win32 Debug (Clang)', 'slavebuilddir': 'win_clang'},
    {'name': 'Win32 Release (Clang)', 'slavebuilddir': 'win_clang'},
    {'name': 'Win64 Debug (Clang)', 'slavebuilddir': 'win_clang'},
    {'name': 'Win64 Release (Clang)', 'slavebuilddir': 'win_clang'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'win',
        'slavebuilddir': spec['slavebuilddir'],
      } for spec in specs
  ])
