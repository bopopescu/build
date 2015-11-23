# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='webrtc_android_scheduler',
                            branch='master',
                            treeStableTimer=0,
                            builderNames=[
          'Android32 Builder (dbg)',
          'Android32 ASan (L Nexus6)',
      ]),
  ])

  specs = [
    {'name': 'Android32 Builder (dbg)'},
    {'name': 'Android32 ASan (L Nexus6)'},
    {'name': 'Android32 Tests (L Nexus6)(dbg)'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/standalone'),
        'notify_on_missing': True,
        'category': 'android',
        'slavebuilddir': spec.get('slavebuilddir', 'android'),
      } for spec in specs
  ])
