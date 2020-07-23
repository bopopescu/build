# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.scheduler import Scheduler
from buildbot.scheduler import Triggerable

import collections

# This file contains useful functions for mains whose subordinates run recipes.

def AddSchedulersAndTriggers(buildmain_config=None,
                             subordinate_list=None,
                             scheduler_name=None,
                             branch=None):
  """Adds schedulers and triggers to the BuildmainConfig based on
  the the subordinate_list.

  This function relies on certain structure in the subordinate_list, in
  particular the custom 'triggered_by' property, which is not yet
  commonly used to define triggers.

  Returns a dictionary mapping builder name, for those builders which
  invoke triggers, to the (synthesized) name of the trigger.

  TODO(kbr): this function does not yet support builders with
  multiple subordinates behind them, but could be updated to do so.

  Throws an Exception if a non-existent builder is mentioned in
  another builder's 'triggered_by' property.

  Arguments:

    buildmain_config: a BuildmainConfig into which the
      'schedulers' property will be defined.

    subordinate_list: a SubordinatesList constructed from subordinates.cfg or builders.pyl.

    scheduler_name: the name of the Scheduler for the polling (not
      triggered) builders.
  """
  c = buildmain_config
  polling_builders = []
  # Maps the parent builder to a set of the names of the builders it triggers.
  trigger_map = collections.defaultdict(list)
  # Maps the name of the parent builder to the (synthesized) name of its
  # trigger, wrapped in a list.
  trigger_name_map = {}
  next_group_id = 0
  for subordinate in subordinate_list.subordinates:
    builder = subordinate['builder']
    parent_builder = subordinate.get('triggered_by')
    if parent_builder == 'none':
      # Uses recipe-side triggers. Don't add to trigger maps.
      pass
    elif parent_builder is not None:
      if subordinate_list.GetSubordinate(builder=parent_builder) is None:
        raise Exception('Could not find parent builder %s for builder %s' %
                        (parent_builder, builder))
      trigger_map[parent_builder].append(builder)
      if parent_builder not in trigger_name_map:
        trigger_name_map[parent_builder] = 'trigger_group_%d' % next_group_id
        next_group_id += 1
    else:
      polling_builders.append(builder)
  s_gpu = Scheduler(name=scheduler_name,
                    branch=branch,
                    treeStableTimer=60,
                    builderNames=polling_builders)
  c['schedulers'] = [s_gpu]
  for name, builders in trigger_map.iteritems():
    c['schedulers'].append(Triggerable(name=trigger_name_map[name],
                                       builderNames=builders))
  return trigger_name_map

def AddRecipeBasedBuilders(buildmain_config=None,
                           subordinate_list=None,
                           annotator=None,
                           trigger_name_map=None):
  """Writes builders which use recipes to the BuildmainConfig's
  'builders' list, using the AnnotatorFactory's BaseFactory.
  Specifies some common factory properties for these builders.

  Arguments:

    buildmain_config: a BuildmainConfig into which the
      'builders' property will be defined.

    subordinate_list: a SubordinatesList constructed from subordinates.cfg or builders.pyl.

    annotator: an AnnotatorFactory instance.

    trigger_name_map: the trigger name map returned by
      AddSchedulersAndTriggers, above.
  """
  builders = []
  for subordinate in subordinate_list.subordinates:
    if 'recipe' in subordinate:
      factory_properties = {
        'test_results_server': 'test-results.appspot.com',
        'generate_gtest_json': True,
        'build_config': subordinate['build_config']
      }
      if 'perf_id' in subordinate:
        factory_properties['show_perf_results'] = True
        factory_properties['perf_id'] = subordinate['perf_id']
      name = subordinate['builder']
      builder = {
        'name': name,
        'factory': annotator.BaseFactory(
          subordinate['recipe'],
          factory_properties,
          [trigger_name_map[name]] if name in trigger_name_map else None),
        'gatekeeper': subordinate.get('gatekeeper_categories', ''),
      }
      # Don't specify auto_reboot unless the subordinate does, to let
      # main_utils' default take effect.
      if 'auto_reboot' in subordinate:
        builder['auto_reboot'] = subordinate['auto_reboot']
      builders.append(builder)
  buildmain_config['builders'] = builders
