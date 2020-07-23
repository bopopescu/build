# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_mac_scheduler',
                            branch='main',
                            treeStableTimer=30,
                            builderNames=[
          'Mac64 Debug',
          'Mac64 Release',
          'Mac64 Release [large tests]',
          'Mac64 Debug (GN)',
          'Mac64 Release (GN)',
          'Mac Asan',
          'iOS32 Debug',
          'iOS32 Release',
          'iOS64 Debug',
          'iOS64 Release',
          'iOS32 Simulator Debug',
          'iOS64 Simulator Debug',
      ]),
  ])

  # 'subordinatebuilddir' below is used to reduce the number of checkouts since some
  # of the builders are pooled over multiple subordinate machines.
  specs = [
    {'name': 'Mac64 Debug', 'subordinatebuilddir': 'mac64'},
    {'name': 'Mac64 Release', 'subordinatebuilddir': 'mac64'},
    {
      'name': 'Mac64 Release [large tests]',
      'category': 'compile|baremetal',
      'subordinatebuilddir': 'mac_baremetal',
    },
    {'name': 'Mac64 Debug (GN)', 'subordinatebuilddir': 'mac64_gn'},
    {'name': 'Mac64 Release (GN)', 'subordinatebuilddir': 'mac64_gn'},
    {'name': 'Mac Asan', 'subordinatebuilddir': 'mac_asan'},
    {
      'name': 'iOS32 Debug',
      'subordinatebuilddir': 'mac32',
      'recipe': 'webrtc/ios',
    },
    {
      'name': 'iOS32 Release',
      'subordinatebuilddir': 'mac32',
      'recipe': 'webrtc/ios',
    },
    {
      'name': 'iOS64 Debug',
      'subordinatebuilddir': 'mac64',
      'recipe': 'webrtc/ios',
    },
    {
      'name': 'iOS64 Release',
      'subordinatebuilddir': 'mac64',
      'recipe': 'webrtc/ios',
    },
    {
      'name': 'iOS32 Simulator Debug',
      'subordinatebuilddir': 'mac32',
      'recipe': 'webrtc/ios',
    },
    {
      'name': 'iOS64 Simulator Debug',
      'subordinatebuilddir': 'mac64',
      'recipe': 'webrtc/ios',
    },
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(spec.get('recipe',
                                                    'webrtc/standalone')),
        'notify_on_missing': True,
        'category': spec.get('category', 'compile|testers'),
        'subordinatebuilddir': spec['subordinatebuilddir'],
      } for spec in specs
  ])
