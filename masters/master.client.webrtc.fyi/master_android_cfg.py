# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from main.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_android_scheduler',
                            branch='main',
                            treeStableTimer=0,
                            builderNames=[
          'Android32 Builder',
          'Android32 ASan (L Nexus6)',
      ]),
  ])

  specs = [
    {'name': 'Android32 Builder'},
    {'name': 'Android32 ASan (L Nexus6)'},
    {'name': 'Android32 Tests (J Nexus4)'},
    {'name': 'Android32 Tests (K Nexus5)'},
    {'name': 'Android32 Tests (L Nexus6)'},
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
