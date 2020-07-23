#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility class to generate a Dartino-specific BuildFactory.

Based on gclient_factory.py.
"""

from buildbot.steps import trigger

from main.factory import gclient_factory
from main.factory.dart import dart_commands

class DartinoFactory(gclient_factory.GClientFactory):
  def __init__(self, build_dir='sdk', target_platform='posix'):
    self.target_platform = target_platform
    self._build_dir = build_dir
    deps_url = 'https://github.com/dartino/sdk.git'
    main = gclient_factory.GClientSolution(deps_url, custom_deps_list=[])
    gclient_factory.GClientFactory.__init__(self, build_dir, [main],
                                            target_platform=target_platform)

  def DartinoAnnotatedFactory(self, python_script, target='Release',
                              env=None, trigger_schedulers=None):
    factory_properties = {
      # Make sure that pulled in projects have the right revision based on date.
      'gclient_transitive': True,

      # Don't set branch part on the --revision flag - we don't use standard
      # chromium layout and hence this is doing the wrong thing.
      'no_gclient_branch': True,

      # We need to set this to False in order to get a --revision=<git-hash>
      # parameter for the gclient update step.
      'no_gclient_revision': False,
    }

    # Create the spec for the solutions
    gclient_spec = self.BuildGClientSpec()

    factory = self.BaseFactory(gclient_spec,
                               factory_properties=factory_properties)

    # Get the factory command object to create new steps to the factory.
    dart_cmd_obj = dart_commands.DartCommands(factory,
                                              target,
                                              self._build_dir,
                                              self.target_platform,
                                              env=env)
    task_kill = 'third_party/dart/tools/task_kill.py'
    dart_cmd_obj.AddKillStep(step_name='Taskkill before running',
                             task_kill_location=task_kill)
    dart_cmd_obj.AddAnnotatedSteps(python_script)
    dart_cmd_obj.AddKillStep(step_name='Taskkill after running',
                             task_kill_location=task_kill)

    if trigger_schedulers:
      dart_cmd_obj.AddTrigger(trigger.Trigger(
          schedulerNames=trigger_schedulers,
          waitForFinish=False,
          updateSourceStamp=False))

    return factory

