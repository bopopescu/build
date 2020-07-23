# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib

from recipe_engine import recipe_api
from recipe_engine.config_types import Path

class EmulatorApi(recipe_api.RecipeApi):

  def install_emulator_deps(self, api_level, **kwargs):
    args = [
        '--api-level', api_level,
    ]
    return self.m.python('[emulator] installing emulator deps',
                         self.c.install_emulator_deps_path, args, **kwargs)

  def wait_for_emulator(self, num, **kwargs):
    args = ['wait', '-n', num]
    self.m.python(
        '[emulator] wait for %d emulators to complete booting' % num,
        self.c.avd_script_path,
        args,
        **kwargs)

  @contextlib.contextmanager
  def launch_emulator(self, abi, api_level, amount=1, partition_size=None,
                      sdcard_size=None, **kwargs):
    launch_step_name = (
        '[emulator] spawn %s %s (abi %s, api_level %s)'
         % (amount, "emulator" if amount == 1 else "emulators", abi, api_level))
    args = [
        'run',
        '--abi', abi,
        '--api-level', api_level,
        '--num', amount,
        '--headless',
        '--enable-kvm',
    ]
    if partition_size:
      args += ['--partition-size', partition_size]
    if sdcard_size:
      args += ['--sdcard-size', sdcard_size]

    self.m.step(
        launch_step_name,
        [self.package_repo_resource('scripts', 'subordinate', 'daemonizer.py'), '--',
         self.c.avd_script_path] + args,
        **kwargs)

    try:
      yield
    finally:
      exit_args = ['kill']
      self.m.python('[emulator] killing all emulators', self.c.avd_script_path,
                    exit_args)
      delete_avd_args = ['delete']
      self.m.python('[emulator] deleting all temp avds after running',
                    self.c.avd_script_path, delete_avd_args)
