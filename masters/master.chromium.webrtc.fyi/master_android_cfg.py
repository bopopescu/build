# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.changes.filter import ChangeFilter
from buildbot.scheduler import Periodic
from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  buildernames_list = [
      'Android Builder (dbg)',
      'Android Builder ARM64 (dbg)',
      'Android GN',
      'Android GN (dbg)',
  ]
  c['schedulers'].extend([
      SingleBranchScheduler(name='android_webrtc_scheduler',
                            change_filter=ChangeFilter(project='webrtc',
                                                       branch='master'),
                            treeStableTimer=0,
                            builderNames=buildernames_list),
      Periodic(name='android_periodic_scheduler',
               periodicBuildTimer=30*60,
               builderNames=buildernames_list),
  ])

  specs = [
    {'name': 'Android Builder (dbg)'},
    {
      'name': 'Android Builder ARM64 (dbg)',
      'slavebuilddir': 'android_arm64',
    },
    {'name': 'Android Tests (dbg) (J Nexus4)'},
    {'name': 'Android Tests (dbg) (K Nexus5)'},
    {'name': 'Android Tests (dbg) (L Nexus5)'},
    {'name': 'Android Tests (dbg) (L Nexus6)'},
    {'name': 'Android Tests (dbg) (L Nexus7.2)'},
    {'name': 'Android Tests (dbg) (L Nexus9)'},
    {
      'name': 'Android GN',
      'recipe': 'chromium_gn',
      'slavebuilddir': 'android_gn',
    },
    {
      'name': 'Android GN (dbg)',
      'recipe': 'chromium_gn',
      'slavebuilddir': 'android_gn',
    },
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory(spec.get('recipe',
                                                    'webrtc/chromium')),
        'category': 'android',
        'notify_on_missing': True,
        'slavebuilddir': spec.get('slavebuilddir', 'android'),
      } for spec in specs
  ])
