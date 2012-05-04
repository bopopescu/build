# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility class to build the swarm master BuildFactory's.

Based on chromium_factory.py and adds chromium-specific steps."""

import os

from master.factory import chromium_factory
from master.factory import swarm_commands

class SwarmFactory(chromium_factory.ChromiumFactory):
  def SwarmFactory(self, target='Release', clobber=False, tests=None,
                   mode=None, slave_type='BuilderTester',
                   options=None, compile_timeout=1200, build_url=None,
                   project=None, factory_properties=None, gclient_deps=None):
    # Do not pass the tests to the ChromiumFactory, they'll be processed below.
    factory = self.ChromiumFactory(target, clobber, [], mode, slave_type,
                                   options, compile_timeout, build_url, project,
                                   factory_properties, gclient_deps)

    swarm_command_obj = swarm_commands.SwarmCommands(factory,
                                                     target,
                                                     self._build_dir,
                                                     self._target_platform)

    gclient_env = factory_properties.get("gclient_env")
    swarm_server = factory_properties.get('swarm_server',
                                          'http://localhost:9001')
    gyp_defines = gclient_env['GYP_DEFINES']
    if 'tests_run=hashtable' in gyp_defines:
      if self._target_platform == 'win32':
        out_dir = 'build'
      elif self._target_platform == 'darwin':
        out_dir = 'xcodebuild'
      else:
        out_dir = 'out'

      # Send of all the test requests as a single step.
      swarm_inputs = [os.path.join('src', out_dir, target, test + '.results')
                      for test in tests]
      swarm_command_obj.AddTriggerSwarmTestStep(self._target_platform,
            swarm_server,
            factory_properties.get('min_swarm_shards', '3'),
            factory_properties.get('max_swarm_shards', '3'),
            swarm_inputs)

      # Each test has its output returned as its own step.
      for test in tests:
        swarm_command_obj.AddGetSwarmTestStep(swarm_server, test)

    return factory
