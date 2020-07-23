# Copyright 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.changes.filter import ChangeFilter
from buildbot.schedulers.basic import SingleBranchScheduler
from main.factory import annotator_factory


AF = annotator_factory.AnnotatorFactory()


def _VersionFileFilter(change):
  """A change filter function that disregards all changes that don't
  touch src/syzygy/SYZYGY_VERSION.

  Args:
      change: a buildbot Change object.
  """
  return change.branch == 'main' and 'syzygy/SYZYGY_VERSION' in change.files


# Official build scheduler for Syzygy
official_scheduler = SingleBranchScheduler('syzygy_version',
                                           treeStableTimer=0,
                                           change_filter=ChangeFilter(
                                               filter_fn=_VersionFileFilter),
                                           builderNames=['Syzygy Official'])

# Windows official Release builder
official_builder = {
    'name': 'Syzygy Official',
    'factory': AF.BaseFactory(recipe='syzygy/continuous'),
    'schedulers': 'syzygy_version',
    'auto_reboot': False,
    'category': 'official',
    }


def Update(config, active_main, c):
  c['schedulers'].append(official_scheduler)
  c['builders'].append(official_builder)
