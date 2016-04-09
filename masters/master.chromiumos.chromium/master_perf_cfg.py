# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from master import master_config
from master.factory import annotator_factory, chromeos_factory

from buildbot.schedulers.basic import SingleBranchScheduler as Scheduler

def Builder(factory_obj, board):
  config = '%s-telemetry' % (board,)
  builder = {
      'name': config,
      'builddir': config,
      'category': '5chromiumos perf',
      'factory': chromeos_factory.ChromiteRecipeFactory(
          factory_obj, 'cros/cbuildbot'),
      'gatekeeper': 'crosperf',
      'scheduler': 'chromium_src_perf',
      'notify_on_missing': True,
      'properties': {
          'cbb_config': config,
      },
  }
  return builder


def Update(_config, active_master, c):
  factory_obj = annotator_factory.AnnotatorFactory(
      active_master=active_master)

  builders = [
      Builder(factory_obj, 'x86-generic'),
      Builder(factory_obj, 'amd64-generic'),
  ]

  c['schedulers'] += [
      Scheduler(name='chromium_src_perf',
                branch='master',
                treeStableTimer=60,
                builderNames=[b['name'] for b in builders],
      ),
  ]
  c['builders'] += builders
