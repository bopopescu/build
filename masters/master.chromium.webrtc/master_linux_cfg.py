# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.schedulers.basic import SingleBranchScheduler

from master.factory import annotator_factory

m_annotator = annotator_factory.AnnotatorFactory()

def Update(c):
  c['schedulers'].extend([
      SingleBranchScheduler(name='linux_rel_scheduler',
                            branch='master',
                            treeStableTimer=60,
                            builderNames=['Linux Builder']),
  ])
  specs = [
    {'name': 'Linux Builder'},
    {'name': 'Linux Tester'},
  ]

  c['builders'].extend([
      {
        'name': spec['name'],
        'factory': m_annotator.BaseFactory('webrtc/chromium'),
        'category': 'linux',
        'notify_on_missing': True,
      } for spec in specs
  ])
