# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='libyuv_mac_scheduler',
                            branch='main',
                            treeStableTimer=0,
                            builderNames=[
          'Mac64 Debug',
          'Mac64 Release',
          'Mac64 Debug (GN)',
          'Mac64 Release (GN)',
          'Mac Asan',
          'iOS Debug',
          'iOS Release',
          'iOS ARM64 Debug',
          'iOS ARM64 Release',
      ]),
  ])

  specs = [
    {'name': 'Mac64 Debug', 'subordinatebuilddir': 'mac64'},
    {'name': 'Mac64 Release', 'subordinatebuilddir': 'mac64'},
    {'name': 'Mac64 Debug (GN)', 'subordinatebuilddir': 'mac64_gn'},
    {'name': 'Mac64 Release (GN)', 'subordinatebuilddir': 'mac64_gn'},
    {'name': 'Mac Asan', 'subordinatebuilddir': 'mac_asan'},
    {'name': 'iOS Debug', 'subordinatebuilddir': 'mac32'},
    {'name': 'iOS Release', 'subordinatebuilddir': 'mac32'},
    {'name': 'iOS ARM64 Debug', 'subordinatebuilddir': 'mac64'},
    {'name': 'iOS ARM64 Release', 'subordinatebuilddir': 'mac64'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('libyuv/libyuv'),
        'notify_on_missing': True,
        'category': 'mac',
        'subordinatebuilddir': spec['subordinatebuilddir'],
      } for spec in specs
  ])
