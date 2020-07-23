# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_android_scheduler',
                            branch='main',
                            treeStableTimer=30,
                            builderNames=[
          'Android32 Builder',
          'Android32 Builder (dbg)',
          'Android32 Builder x86 (dbg)',
          'Android32 Builder MIPS (dbg)',
          'Android32 Clang (dbg)',
          'Android64 Builder',
          'Android64 Builder (dbg)',
          'Android64 Builder x64 (dbg)',
          'Android32 GN',
          'Android32 GN (dbg)',
      ]),
  ])

  # 'subordinatebuilddir' below is used to reduce the number of checkouts since some
  # of the builders are pooled over multiple subordinate machines.
  specs = [
    {'name': 'Android32 Builder'},
    {'name': 'Android32 Builder (dbg)'},
    {'name': 'Android32 Builder x86 (dbg)', 'subordinatebuilddir': 'android_x86'},
    {'name': 'Android32 Builder MIPS (dbg)', 'subordinatebuilddir': 'android_mips'},
    {'name': 'Android32 Clang (dbg)', 'subordinatebuilddir': 'android_clang'},
    {'name': 'Android64 Builder', 'subordinatebuilddir': 'android_arm64'},
    {'name': 'Android64 Builder (dbg)', 'subordinatebuilddir': 'android_arm64'},
    {'name': 'Android64 Builder x64 (dbg)', 'subordinatebuilddir': 'android_x64'},
    {'name': 'Android32 GN', 'subordinatebuilddir': 'android_gn'},
    {'name': 'Android32 GN (dbg)', 'subordinatebuilddir': 'android_gn'},
    {'name': 'Android32 Tests (L Nexus5)(dbg)'},
    {'name': 'Android32 Tests (L Nexus7.2)(dbg)'},
    {'name': 'Android64 Tests (L Nexus9)'},
    {'name': 'Android32 Tests (L Nexus5)'},
    {'name': 'Android32 Tests (L Nexus7.2)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'android',
        'subordinatebuilddir': spec.get('subordinatebuilddir', 'android'),
      } for spec in specs
  ])
