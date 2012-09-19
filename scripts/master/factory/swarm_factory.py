# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility class to build the swarm master BuildFactory's.

Based on chromium_factory.py and adds chromium-specific steps."""

from buildbot.process import factory

from master.factory import chromium_factory
from master.factory import swarm_commands

import config


class SwarmTest(object):
  """A small helper class containing any required details to run a
     swarm test.
  """
  def __init__(self, test_name, shards):
    self.test_name = test_name
    self.shards = shards


SWARM_TESTS = [
    # They must be in the reverse order of latency to get results, e.g. the
    # slowest test should be last.
    SwarmTest('base_unittests', 1),
    SwarmTest('net_unittests', 3),
    SwarmTest('unit_tests', 4),
    SwarmTest('browser_tests', 5),
]


def SetupSwarmTests(machine, data_dir, options=None, project=None,
                    network_path=None, extra_gyp_defines='', ninja=False):
  """This is a swarm builder."""
  factory_properties = {
    'gclient_env' : {
      'GYP_DEFINES': (
        'test_isolation_mode=hashtable '
        'test_isolation_outdir=' + data_dir +
        ' ' + extra_gyp_defines +
        ' disable_nacl=1'
        ' fastbuild=1'
      ),
      'GYP_MSVS_VERSION': '2010',
    },
    'data_dir': data_dir,
    'swarm_server': config.Master.swarm_server_internal_url
  }
  if ninja:
    factory_properties['gclient_env']['GYP_GENERATORS'] = 'ninja'
    # Build until death.
    options = ['--build-tool=ninja'] + options + ['--', '-k', '0']

  return machine.SwarmFactory(
      tests=SWARM_TESTS,
      options=options,
      project=project,
      factory_properties=factory_properties,
      network_path=network_path)


def SwarmTestBuilder(swarm_server):
  """Create a basic swarm builder that runs tests via swarm."""
  f = factory.BuildFactory()

  swarm_command_obj = swarm_commands.SwarmCommands(f)

  # Send the swarm tests to the swarm server.
  swarm_command_obj.AddTriggerSwarmTestStep(
      swarm_server=swarm_server,
      tests=SWARM_TESTS,
      doStepIf=swarm_commands.TestStepHasSwarmProperties)

  # Collect the results
  for swarm_test in SWARM_TESTS:
    swarm_command_obj.AddGetSwarmTestStep(swarm_server, swarm_test.test_name)

  return f


class SwarmFactory(chromium_factory.ChromiumFactory):
  def SwarmFactory(self, target='Release', clobber=False, tests=None,
                   mode=None, options=None, compile_timeout=1200,
                   build_url=None, project=None, factory_properties=None,
                   gclient_deps=None, network_path=None):
    # Do not pass the tests to the ChromiumFactory, they'll be processed below.
    # Set the slave_type to 'SwarmSlave' to prevent the factory from adding the
    # compile step, so we can add other steps before the compile step.
    f = self.ChromiumFactory(target, clobber, [], mode, 'SwarmSlave',
                             options, compile_timeout, build_url, project,
                             factory_properties, gclient_deps)

    swarm_command_obj = swarm_commands.SwarmCommands(f,
                                                     target,
                                                     self._build_dir,
                                                     self._target_platform)

    # Ensure the network drive is mapped on windows.
    data_dir = factory_properties.get('data_dir')
    if self._target_platform == 'win32':
      swarm_command_obj.SetupWinNetworkDrive(data_dir[:2], network_path)

    # Now add the compile step.
    swarm_command_obj.AddCompileStep(
        project or self._project, clobber,
        mode=mode,
        options=options,
        timeout=compile_timeout,
        haltOnFailure=False)

    gclient_env = factory_properties.get('gclient_env')
    swarm_server = factory_properties.get('swarm_server',
                                          'http://localhost:9001')
    swarm_server = swarm_server.rstrip('/')

    gyp_defines = gclient_env['GYP_DEFINES']
    if 'test_isolation_mode=hashtable' in gyp_defines:
      test_names = [test.test_name for test in tests]

      swarm_command_obj.AddGenerateResultHashesStep(
          using_ninja='--build-tool=ninja' in (options or []),
          tests=test_names)

      # Send of all the test requests as a single step.
      swarm_command_obj.AddTriggerSwarmTestStep(swarm_server, tests)

      # Each test has its output returned as its own step.
      for test in tests:
        swarm_command_obj.AddGetSwarmTestStep(swarm_server, test.test_name)

    return f
