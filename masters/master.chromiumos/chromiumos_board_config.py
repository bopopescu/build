# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import sys

from common.cros_chromite import Get, ChromiteTarget
from common.subordinate_alloc import SubordinateAllocator
from main.cros import builder_config


# Declare a subordinate allocator. We do this here so we can access the subordinates
# configured by 'subordinates.cfg' in 'main.cfg'.
subordinate_allocator = SubordinateAllocator(list_unallocated=True)


# Get the pinned Chromite configuration.
cbb_config = Get(allow_fetch=True)


# Select any board that is configured to build on this waterfall.
def _GetWaterfallTargets():
  result = collections.OrderedDict()
  for config in cbb_config.itervalues():
    if config.get('active_waterfall') != 'chromiumos':
      continue
    result[config.name] = config
  return result
waterfall_targets = _GetWaterfallTargets()


# Load the builder configs.
builder_configs = builder_config.GetBuilderConfigs(waterfall_targets)
builder_name_map = dict((c.builder_name, c)
                        for c in builder_configs.itervalues())
