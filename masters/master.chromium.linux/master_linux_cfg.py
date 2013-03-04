# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from master import master_config
from master.factory import chromium_factory

defaults = {}

helper = master_config.Helper(defaults)
B = helper.Builder
F = helper.Factory
S = helper.Scheduler
T = helper.Triggerable

def linux():
  return chromium_factory.ChromiumFactory('src/out', 'linux2')
def linux_tester():
  return chromium_factory.ChromiumFactory(
      'src/out', 'linux2', nohooks_on_update=True)

# Tests that are single-machine shard-safe.
sharded_tests = [
  'aura_unittests',
  'base_unittests',
  'browser_tests',
  'cacheinvalidation_unittests',
  'cc_unittests',
  'chromedriver2_tests',
  'chromedriver2_unittests',
  'components_unittests',
  'content_browsertests',
  # http://crbug.com/178006
  #'content_unittests',
  'crypto_unittests',
  'device_unittests',
  # http://crbug.com/178005
  #'gpu_unittests',
  'jingle_unittests',
  'media_unittests',
  'net_unittests',
  'ppapi_unittests',
  'printing_unittests',
  'remoting_unittests',
  'sync_integration_tests',
  'sync_unit_tests',
  'ui_unittests',
  # http://crbug.com/177927
  #'unit_tests',
  'views_unittests',
  'webkit_compositor_bindings_unittests',
]

# These are the common targets to most of the builders
linux_all_test_targets = [
  'base_unittests',
  'browser_tests',
  'cacheinvalidation_unittests',
  'cc_unittests',
  'chrome',
  'chromedriver2_unittests',
  'components_unittests',
  'content_browsertests',
  'content_unittests',
  'crypto_unittests',
  'dbus_unittests',
  'device_unittests',
  'googleurl_unittests',
  'gpu_unittests',
  'interactive_ui_tests',
  'ipc_tests',
  'jingle_unittests',
  'media_unittests',
  'net_unittests',
  'ppapi_unittests',
  'printing_unittests',
  'remoting_unittests',
  'sandbox_linux_unittests',
  'sql_unittests',
  'sync_unit_tests',
  'ui_unittests',
  'unit_tests',
  'webkit_compositor_bindings_unittests',
]


################################################################################
## Release
################################################################################

defaults['category'] = '4linux'

rel_archive = master_config.GetArchiveUrl('ChromiumLinux', 'Linux Builder x64',
                                          'Linux_Builder_x64', 'linux')
rel_precise_archive = master_config.GetArchiveUrl(
    'ChromiumLinux', 'Linux Builder (Precise)',
    'Linux_Builder__Precise_', 'linux')

#
# Main release scheduler for src/
#
S('linux_rel', branch='src', treeStableTimer=60)

#
# Triggerable scheduler for the rel builder
#
T('linux_rel_trigger')
T('linux_rel_precise_trigger')

#
# Linux Rel Builder
#
B('Linux Builder x64', 'rel', 'compile', 'linux_rel',
  auto_reboot=False, notify_on_missing=True)
F('rel', linux().ChromiumFactory(
    slave_type='Builder',
    options=['--compiler=goma',] + linux_all_test_targets +
            ['sync_integration_tests'],
    tests=['check_deps'],
    factory_properties={'trigger': 'linux_rel_trigger'}))

B('Linux Builder (Precise)', 'rel_precise', 'compile', 'linux_rel',
  auto_reboot=False, notify_on_missing=True)
F('rel_precise', linux().ChromiumFactory(
    slave_type='Builder',
    options=['--compiler=goma',] + linux_all_test_targets +
            ['sync_integration_tests'],
    tests=['check_deps'],
    factory_properties={'trigger': 'linux_rel_precise_trigger'}))

#
# Linux Rel testers
#
B('Linux Tests x64', 'rel_unit', 'testers', 'linux_rel_trigger',
  notify_on_missing=True)
F('rel_unit', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=rel_archive,
    tests=[
      'base_unittests',
      'browser_tests',
      'cacheinvalidation',
      'cc_unittests',
      'chromedriver2_unittests',
      'components_unittests',
      'content_browsertests',
      'content_unittests',
      'crypto',
      'dbus',
      'device_unittests',
      'googleurl',
      'gpu',
      'interactive_ui_tests',
      'ipc_tests',
      'jingle',
      'media',
      'net',
      'ppapi_unittests',
      'printing',
      'remoting',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
      'webkit_compositor_bindings_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

B('Linux Tests (Precise)',
  'rel_precise_unit',
  'testers',
  'linux_rel_precise_trigger',
  notify_on_missing=True)
F('rel_precise_unit', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=rel_precise_archive,
    tests=[
      'base_unittests',
      'browser_tests',
      'cacheinvalidation',
      'cc_unittests',
      'chromedriver2_unittests',
      'components_unittests',
      'content_browsertests',
      'content_unittests',
      'crypto',
      'dbus',
      'device_unittests',
      'googleurl',
      'gpu',
      'interactive_ui_tests',
      'ipc_tests',
      'jingle',
      'media',
      'net',
      'ppapi_unittests',
      'printing',
      'remoting',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
      'webkit_compositor_bindings_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

B('Linux Sync', 'rel_sync', 'testers', 'linux_rel_trigger',
  notify_on_missing=True)
F('rel_sync', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=rel_archive,
    tests=['sync_integration'],
    factory_properties={'generate_gtest_json': True}))

B('Linux Sync (Precise)',
  'rel_precise_sync',
  'testers',
  'linux_rel_precise_trigger',
  notify_on_missing=True)
F('rel_precise_sync', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=rel_precise_archive,
    tests=['sync_integration'],
    factory_properties={
      'generate_gtest_json': True,
      'sharded_tests': sharded_tests,
    }))

#
# Linux aura bot
#

linux_aura_tests = [
  'aura',
  'base_unittests',
  'browser_tests',
  'cacheinvalidation',
  'compositor',
  'content_browsertests',
  'content_unittests',
  'crypto',
  'device_unittests',
  'googleurl',
  'gpu',
  'interactive_ui_tests',
  'ipc_tests',
  'jingle',
  'media',
  'net',
  'ppapi_unittests',
  'printing',
  'remoting',
  'sandbox_linux_unittests',
  'ui_unittests',
  'unit_sql',
  'unit_sync',
  'unit_unit',
  'views',
]

linux_aura_options=[
  'aura_builder',
  'base_unittests',
  'browser_tests',
  'cacheinvalidation_unittests',
  'chrome',
  'compositor_unittests',
  'content_browsertests',
  'content_unittests',
  'crypto_unittests',
  'device_unittests',
  'googleurl_unittests',
  'gpu_unittests',
  'interactive_ui_tests',
  'ipc_tests',
  'jingle_unittests',
  'media_unittests',
  'net_unittests',
  'ppapi_unittests',
  'printing_unittests',
  'remoting_unittests',
  'sandbox_linux_unittests',
  'sql_unittests',
  'ui_unittests',
]

B('Linux Aura', 'f_linux_rel_aura', 'compile', 'linux_rel',
  notify_on_missing=True)
B('Linux Aura (Precise)', 'f_linux_rel_aura', 'compile', 'linux_rel',
  notify_on_missing=True)
F('f_linux_rel_aura', linux().ChromiumFactory(
    target='Release',
    slave_type='BuilderTester',
    options=['--compiler=goma'] + linux_aura_options,
    tests=linux_aura_tests,
    factory_properties={
      'gclient_env': {'GYP_DEFINES': 'use_aura=1'},
      'sharded_tests': sharded_tests,
      'window_manager': 'False',
    }))


################################################################################
## Debug
################################################################################

#
# Main debug scheduler for src/
#
S('linux_dbg', branch='src', treeStableTimer=60)

dbg_archive = master_config.GetArchiveUrl('ChromiumLinux',
                                          'Linux Builder (dbg)',
                                          'Linux_Builder__dbg_', 'linux')
dbg_precise_archive = master_config.GetArchiveUrl(
    'ChromiumLinux',
    'Linux Builder (dbg)(Precise)',
    'Linux_Builder__dbg__Precise_', 'linux')

#
# Triggerable scheduler for the dbg builders
#
T('linux_dbg_trigger')
T('linux_dbg_precise_trigger')

#
# Linux Dbg Builder
#
B('Linux Builder (dbg)', 'dbg', 'compile', 'linux_dbg',
  auto_reboot=False, notify_on_missing=True)
F('dbg', linux().ChromiumFactory(
    slave_type='Builder',
    target='Debug',
    options=['--compiler=goma'] + linux_all_test_targets,
    factory_properties={'trigger': 'linux_dbg_trigger',
                        'gclient_env': {'GYP_DEFINES':'target_arch=ia32'},}))

#
# Linux Dbg Unit testers
#

B('Linux Tests (dbg)(1)', 'dbg_unit_1', 'testers', 'linux_dbg_trigger',
  notify_on_missing=True)
# TODO(phajdan.jr): Add the Precise bot to gatekeeper.
B('Linux Tests (dbg)(1)(Precise 32)',
    factory='dbg_unit_1',
    scheduler='linux_dbg_trigger',
    notify_on_missing=True)
F('dbg_unit_1', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=dbg_archive,
    target='Debug',
    tests=[
      'browser_tests',
      'content_browsertests',
      'net',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

B('Linux Tests (dbg)(2)', 'dbg_unit_2', 'testers', 'linux_dbg_trigger',
  notify_on_missing=True)
# TODO(phajdan.jr): Add the Precise bot to gatekeeper.
B('Linux Tests (dbg)(2)(Precise 32)',
    factory='dbg_unit_2',
    scheduler='linux_dbg_trigger',
    notify_on_missing=True)
F('dbg_unit_2', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=dbg_archive,
    target='Debug',
    tests=[
      'base_unittests',
      'cacheinvalidation',
      'cc_unittests',
      'chromedriver2_unittests',
      'components_unittests',
      'content_unittests',
      'crypto',
      'dbus',
      'device_unittests',
      'googleurl',
      'gpu',
      'interactive_ui_tests',
      'ipc_tests',
      'jingle',
      'media',
      'nacl_integration',
      'ppapi_unittests',
      'printing',
      'remoting',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
      'webkit_compositor_bindings_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

B('Linux Builder (dbg)(Precise)', 'dbg_precise', 'compile', 'linux_dbg',
  auto_reboot=False, notify_on_missing=True)
F('dbg_precise', linux().ChromiumFactory(
    slave_type='Builder',
    target='Debug',
    options=['--compiler=goma'] + linux_all_test_targets,
    factory_properties={'trigger': 'linux_dbg_precise_trigger'}))

# TODO(phajdan.jr): Add the Precise bot to gatekeeper.
B('Linux Tests (dbg)(1)(Precise)',
    factory='dbg_precise_unit_1',
    scheduler='linux_dbg_precise_trigger',
    notify_on_missing=True)
F('dbg_precise_unit_1', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=dbg_precise_archive,
    target='Debug',
    tests=[
      'browser_tests',
      'content_browsertests',
      'net',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

# TODO(phajdan.jr): Add the Precise bot to gatekeeper.
B('Linux Tests (dbg)(2)(Precise)',
    factory='dbg_precise_unit_2',
    scheduler='linux_dbg_precise_trigger',
    notify_on_missing=True)
F('dbg_precise_unit_2', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=dbg_precise_archive,
    target='Debug',
    tests=[
      'base_unittests',
      'cacheinvalidation',
      'cc_unittests',
      'chromedriver2_unittests',
      'components_unittests',
      'content_unittests',
      'crypto',
      'dbus',
      'device_unittests',
      'googleurl',
      'gpu',
      'interactive_ui_tests',
      'ipc_tests',
      'jingle',
      'media',
      'nacl_integration',
      'ppapi_unittests',
      'printing',
      'remoting',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
      'webkit_compositor_bindings_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

#
# Linux Precise bot. Running Ubuntu 12.04, used for testing sandboxing with
# seccomp-bpf.
#

B('Linux Precise (dbg)', 'dbg_precise_1', 'testers', 'linux_dbg_trigger',
  auto_reboot=True, notify_on_missing=True)
F('dbg_precise_1', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=dbg_archive,
    target='Debug',
    tests=[
      'base_unittests',
      'browser_tests',
      'content_browsertests',
      'sandbox_linux_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

B('Linux Precise x64', 'rel_precise_1', 'testers', 'linux_rel_trigger',
  auto_reboot=True, notify_on_missing=True)
F('rel_precise_1', linux_tester().ChromiumFactory(
    slave_type='Tester',
    build_url=rel_archive,
    tests=[
      'base_unittests',
      'browser_tests',
      'content_browsertests',
      'sandbox_linux_unittests',
    ],
    factory_properties={'sharded_tests': sharded_tests,
                        'generate_gtest_json': True}))

#
# Linux Dbg Clang bot
#

B('Linux Clang (dbg)', 'dbg_linux_clang', 'compile', 'linux_dbg',
  notify_on_missing=True)
F('dbg_linux_clang', linux().ChromiumFactory(
    target='Debug',
    options=['--build-tool=ninja', '--compiler=goma-clang'],
    tests=[
      'base_unittests',
      'components_unittests',
      'content_unittests',
      'crypto',
      'device_unittests',
      'ipc_tests',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
    ],
    factory_properties={
      'gclient_env': {
        'GYP_GENERATORS':'ninja',
        'GYP_DEFINES':
          'clang=1 clang_use_chrome_plugins=1 fastbuild=1 '
            'test_isolation_mode=noop',
    }}))

B('Linux Clang (dbg)(Precise)',
  'dbg_precise_linux_clang',
  'compile',
  'linux_dbg',
  notify_on_missing=True)
F('dbg_precise_linux_clang', linux().ChromiumFactory(
    target='Debug',
    options=['--build-tool=ninja', '--compiler=goma-clang'],
    tests=[
      'base_unittests',
      'components_unittests',
      'content_unittests',
      'crypto',
      'device_unittests',
      'ipc_tests',
      'sandbox_linux_unittests',
      'ui_unittests',
      'unit_sql',
      'unit_sync',
      'unit_unit',
    ],
    factory_properties={
      'gclient_env': {
        'GYP_GENERATORS':'ninja',
        'GYP_DEFINES':
          'clang=1 clang_use_chrome_plugins=1 fastbuild=1 '
            'test_isolation_mode=noop',
      },
      'sharded_tests': sharded_tests,
    }))


def Update(config, active_master, c):
  return helper.Update(c)
