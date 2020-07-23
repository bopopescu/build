# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='libyuv_windows_scheduler',
                            branch='main',
                            treeStableTimer=0,
                            builderNames=[
          'Win32 Debug (VS2010)',
          'Win32 Release (VS2010)',
          'Win64 Debug (VS2010)',
          'Win64 Release (VS2010)',
          'Win32 Debug (VS2012)',
          'Win32 Release (VS2012)',
          'Win64 Debug (VS2012)',
          'Win64 Release (VS2012)',
          'Win32 Debug (VS2013)',
          'Win32 Release (VS2013)',
          'Win64 Debug (VS2013)',
          'Win64 Release (VS2013)',
          'Win32 Debug (Clang)',
          'Win32 Release (Clang)',
          'Win64 Debug (Clang)',
          'Win64 Release (Clang)',
          'Win64 Debug (GN)',
          'Win64 Release (GN)',
      ]),
  ])

  specs = [
    {'name': 'Win32 Debug (VS2010)', 'subordinatebuilddir': 'win_2010'},
    {'name': 'Win32 Release (VS2010)', 'subordinatebuilddir': 'win_2010'},
    {'name': 'Win64 Debug (VS2010)', 'subordinatebuilddir': 'win_2010'},
    {'name': 'Win64 Release (VS2010)', 'subordinatebuilddir': 'win_2010'},
    {'name': 'Win32 Debug (VS2012)', 'subordinatebuilddir': 'win_2012'},
    {'name': 'Win32 Release (VS2012)', 'subordinatebuilddir': 'win_2012'},
    {'name': 'Win64 Debug (VS2012)', 'subordinatebuilddir': 'win_2012'},
    {'name': 'Win64 Release (VS2012)', 'subordinatebuilddir': 'win_2012'},
    {'name': 'Win32 Debug (VS2013)', 'subordinatebuilddir': 'win_2013'},
    {'name': 'Win32 Release (VS2013)', 'subordinatebuilddir': 'win_2013'},
    {'name': 'Win64 Debug (VS2013)', 'subordinatebuilddir': 'win_2013'},
    {'name': 'Win64 Release (VS2013)', 'subordinatebuilddir': 'win_2013'},
    {'name': 'Win32 Debug (Clang)', 'subordinatebuilddir': 'win_clang'},
    {'name': 'Win32 Release (Clang)', 'subordinatebuilddir': 'win_clang'},
    {'name': 'Win64 Debug (Clang)', 'subordinatebuilddir': 'win_clang'},
    {'name': 'Win64 Release (Clang)', 'subordinatebuilddir': 'win_clang'},
    {'name': 'Win64 Debug (GN)', 'subordinatebuilddir': 'win64_gn'},
    {'name': 'Win64 Release (GN)', 'subordinatebuilddir': 'win64_gn'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('libyuv/libyuv'),
        'notify_on_missing': True,
        'category': 'win',
        'subordinatebuilddir': spec['subordinatebuilddir'],
      } for spec in specs
  ])
