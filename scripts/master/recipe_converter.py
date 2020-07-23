# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import main.chromium_step
import main.log_parser.retcode_command
import main.log_parser.webkit_test_command
import main.factory.commands
import main.factory.drmemory_factory
import main.main_utils
import buildbot.process.properties
import buildbot.steps.transfer
import buildbot.steps.shell
import buildbot.steps.trigger
import sys
import collections
import cStringIO
import pprint
import buildbot
import logging
import datetime

# Terrible hack; to enable converting triggers.
_GLOBAL_BUILDMASTER_CONFIG = None

_main_builder_map = {
    'NativeClientSDK': ['windows-sdk-multi',
                        'mac-sdk-multi',
                        'linux-sdk-multi',
                        'linux-sdk-asan-multi',
                        'windows-sdk-multirel',
                        'mac-sdk-multirel',
                        'linux-sdk-multirel',
                       ],
    'DrMemory':   ['linux-builder',
                   'win-builder',
                   'win-xp-drm',
                   'win-vista_x64-drm',
                   'win-7_x64-drm',
                   'win-8_x64-drm',
                   'linux-lucid_x64-drm',
                   'mac-builder',
                   'mac-mavericks_x64-drm',
                   'mac-builder-DR',
                   'mac-mavericks_x64-DR',
                   'win7-cr-builder',
                   'win7-cr',
                   'win8-cr-builder',
                   'win8-cr',
                   'linux-cr-builder',
                   'linux-cr',
                  ],
    'Chromium GPU': ['Android Debug (Nexus 5)',
                     'Android Debug (Nexus 6)',
                     'Android Debug (Nexus 9)',
                    ],
    'Chromium ChromeDriver': ['Win7',
                              'Linux',
                              'Linux32',
                              'Mac 10.6',
                             ],
    'Chromium GPU FYI': ['Win7 Audio',
                         'Linux Audio',
                        ],
    'DynamoRIO': ['win-xp-dr',
                  'win-7-dr',
                  'win-8-dr',
                  'linux-dr',
                  'linux-dr-package',
                  'win-dr-package',
                  'win-xp-dr-nightly',
                  'win-7-dr-nightly',
                  'win-8-dr-nightly',
                  'linux-dr-nightly',
                  ],
    'Dart': ['cross-dartino-linux-arm',
             'dartino-linux-release-x86',
             'dartino-linux-debug-x86',
             'dartino-linux-release-asan-x86',
             'dartino-linux-debug-asan-x86',
             'target-dartino-linux-release-arm',
             'target-dartino-linux-debug-arm',
             'dartino-win-debug-x86',
             'dartino-mac-release-x86',
             'dartino-mac-debug-x86',
             'dartino-mac-release-asan-x86',
             'dartino-mac-debug-asan-x86',
             'dartino-free-rtos',
             'dartino-lk-debug-arm-qemu',
             'dartino-linux-release-x64-sdk',
             'dartino-mac-release-x64-sdk',
             'dartino-linux-release-x86-dev',
             'dartino-linux-debug-x86-dev',
             'dartino-linux-release-asan-x86-dev',
             'dartino-linux-debug-asan-x86-dev',
             'cross-dartino-linux-arm-dev',
             'target-dartino-linux-release-arm-dev',
             'target-dartino-linux-debug-arm-dev',
             'dartino-win-debug-x86-dev',
             'dartino-mac-release-x86-dev',
             'dartino-mac-debug-x86-dev',
             'dartino-mac-release-asan-x86-dev',
             'dartino-mac-debug-asan-x86-dev',
             'dartino-free-rtos-dev',
             'dartino-lk-debug-arm-qemu-dev',
             'dartino-linux-release-x64-sdk-dev',
             'dartino-mac-release-x64-sdk-dev',
            ],
    'Chromium FYI': ['ChromiumOS Linux Tests',
                     'Android ChromeDriver Tests (dbg)',
                     'Android Asan Builder Tests (dbg)',
                     'Blink Linux LSan ASan',
                     'CFI Linux CF',
                    ]
}

_main_name_map = {
    'NativeClientSDK': 'client.nacl.sdk',
    'Chromium GPU': 'chromium.gpu',
    'Chromium ChromeDriver': 'chromium.chromedriver',
    'Chromium GPU FYI': 'chromium.gpu.fyi',
    'DynamoRIO': 'client.dynamorio',
    'Dart': 'client.fletch',
    'DrMemory': 'client.drmemory',
    'Chromium FYI': 'chromium.fyi',
}

# Used like a structure.
class recipe_chunk(object):
  def __init__(self):
    self.deps = set()
    self.steps = list()
    self.tests = set()

  def __repr__(self):
    return pprint.pformat(self.deps, indent=4) + '\n' + \
        pprint.pformat(self.steps, indent=4)

  # Note that addition is *not* commutative; rc1 + rc2 implies that rc1 will be
  # executed first.
  def __add__(self, other):
    s = recipe_chunk()
    s.deps = self.deps | other.deps
    s.tests = self.tests | other.tests
    s.steps = self.steps + other.steps
    return s

_step_signatures = {
  'update_scripts': (buildbot.steps.shell.ShellCommand,
                     {
                       'command': ['gclient', 'sync', '--verbose', '--force'],
                       'description': 'update_scripts',
                       'name': 'update_scripts',
                       'workdir': '../../..'
                     }
                    ),
  'bot_update': (main.chromium_step.AnnotatedCommand,
                 {
                   'command': ['python', '-u',
                               '../../../scripts/subordinate/bot_update.py'],
                   'description': 'bot_update',
                   'name': 'bot_update',
                   'workdir': 'build',
                 }
                ),
  'win_bot_update': (main.chromium_step.AnnotatedCommand,
                 {
                   'command': ['python', '-u',
                               '..\\..\\..\\scripts\\subordinate\\bot_update.py'],
                   'description': 'bot_update',
                   'name': 'bot_update',
                   'workdir': 'build',
                 }
                ),
  'cleanup_temp': (main.log_parser.retcode_command.ReturnCodeCommand,
                   {
                     'command': ['python',
                                 '../../../scripts/subordinate/cleanup_temp.py'],
                     'description': 'cleanup_temp',
                     'name': 'cleanup_temp',
                   }
                  ),
  'win_cleanup_temp': (main.log_parser.retcode_command.ReturnCodeCommand,
      {
        'command': ['python',
                    '..\\..\\..\\scripts\\subordinate\\cleanup_temp.py'],
        'description': 'cleanup_temp',
        'name': 'cleanup_temp',
      }
    ),
  'gclient_update':      (main.chromium_step.GClient,
                          {
                            'mode': 'update',
                          }),
  'gclient_safe_revert': (buildbot.steps.shell.ShellCommand,
                          {
                            'command': ['python',
                              '../../../scripts/subordinate/gclient_safe_revert.py',
                              '.', 'gclient'],
                            'description': 'gclient_revert',
                            'name': 'gclient_revert',
                            'workdir': 'build',
                          }
    ),
  'win_gclient_safe_revert': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\gclient_safe_revert.py',
          '.', 'gclient.bat'],
        'description': 'gclient_revert',
        'name': 'gclient_revert',
        'workdir': 'build',
      }
    ),
  'bb_run_bot':   (main.chromium_step.AnnotatedCommand,
                   {
                     'command': ['python',
                       'src/build/android/buildbot/bb_run_bot.py'],
                     'name': 'subordinate_steps',
                     'description': 'subordinate_steps',
                   }
                  ),
  'gclient_runhooks_wrapper': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['python', '../../../scripts/subordinate/runhooks_wrapper.py'],
        'description': 'gclient hooks',
        'env': {},
        'name': 'runhooks'
        # NOTE: locking shouldn't be required, as only one recipe is ever run on
        # a subordinate at a time; specifically, a SubordinateLock of type subordinate_exclusive
        # *should be* redundant. Noted here in case it isn't. (aneeshm)
      }
    ),
  'win_gclient_runhooks_wrapper': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['python_subordinate',
                    '..\\..\\..\\scripts\\subordinate\\runhooks_wrapper.py'],
        'description': 'gclient hooks',
        'env': {},
        'name': 'runhooks'
        # NOTE: locking shouldn't be required, as only one recipe is ever run on
        # a subordinate at a time; specifically, a SubordinateLock of type subordinate_exclusive
        # *should be* redundant. Noted here in case it isn't. (aneeshm)
      }
    ),
  'chromedriver_buildbot_run': (main.chromium_step.AnnotatedCommand,
      {
        'name': 'annotated_steps',
        'description': 'annotated_steps',
        'command': ['python',
          '../../../scripts/subordinate/chromium/chromedriver_buildbot_run.py'],
      }
    ),
  'win_chromedriver_buildbot_run': (main.chromium_step.AnnotatedCommand,
      {
        'name': 'annotated_steps',
        'description': 'annotated_steps',
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\chromium\\chromedriver_buildbot_run.py'],
      }
    ),
  'compile_py':
    (main.factory.commands.CompileWithRequiredSwarmTargets,
      {
        'command': ['python', '../../../scripts/subordinate/compile.py'],
        'name': 'compile',
        'description': 'compiling',
        'descriptionDone': 'compile',
      }
    ),
  'win_compile_py':
    (main.factory.commands.CompileWithRequiredSwarmTargets,
      {
        'command': ['python_subordinate', '..\\..\\..\\scripts\\subordinate\\compile.py'],
        'name': 'compile',
        'description': 'compiling',
        'descriptionDone': 'compile',
      }
    ),
  'win_svnkill': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['%WINDIR%\\system32\\taskkill', '/f', '/im', 'svn.exe',
                    '||', 'set', 'ERRORLEVEL=0'],
        'description': 'svnkill',
        'name': 'svnkill',
      }
    ),
  'win_update_scripts': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['gclient.bat', 'sync', '--verbose', '--force'],
        'description': 'update_scripts',
        'name': 'update_scripts',
      }
    ),
  'win_taskkill': (main.log_parser.retcode_command.ReturnCodeCommand,
      {
        'command': ['python', '..\\..\\..\\scripts\\subordinate\\kill_processes.py'],
        'name': 'taskkill',
        'description': 'taskkill',
      }
    ),
  'runtest': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python', '../../../scripts/subordinate/runtest.py'],
      }
    ),
  'runtest2': (main.log_parser.webkit_test_command.WebKitCommand,
      {
        'command': ['python', '../../../scripts/subordinate/runtest.py'],
      }
    ),
  'win_runtest': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate', '..\\..\\..\\scripts\\subordinate\\runtest.py'],
      }
    ),
  'clear_tools': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['rd', '/q', '/s', 'buildbot'],
        'name': 'clear tools directory',
        'workdir': 'tools',
      }
    ),
  'checkout_dynamorio': (buildbot.steps.source.Git,
      {
        'branch': 'main',
        'name': 'Checkout DynamoRIO',
        'workdir': 'dynamorio',
        'repourl': 'https://github.com/DynamoRIO/dynamorio.git',
      }
    ),
  'checkout_drmemory': (buildbot.steps.source.Git,
      {
        'branch': 'main',
        'name': 'Checkout Dr. Memory',
        'workdir': 'drmemory',
        'repourl': 'https://github.com/DynamoRIO/drmemory.git',
      }
    ),
  'checkout_dynamorio_tools': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['git', 'clone',
          'https://github.com/DynamoRIO/buildbot.git'],
        'name': 'update tools',
        'workdir': 'tools',
      }
    ),
  'dynamorio_unpack_tools': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['unpack.bat'],
        'name': 'unpack tools',
        'description': 'unpack tools',
        'workdir': 'tools/buildbot/bot_tools',
      }
    ),
  'win_dynamorio_nightly_suite': (main.factory.drmemory_factory.CTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
          'ctest', '--timeout', '120', '-VV', '-S'],
        'name': 'nightly suite',
        'descriptionDone': 'nightly suite',
      }
    ),
  'dynamorio_nightly_suite': (main.factory.drmemory_factory.CTest,
      {
        'command': ['ctest', '--timeout', '120', '-VV', '-S',
          '../dynamorio/suite/runsuite.cmake,nightly;long;'+\
              'site=X64.Linux.VS2010.BuildBot'],
        'descriptionDone': 'nightly suite',
        'name': 'nightly suite',
      }
    ),
  'win_dynamorio_precommit':(main.factory.drmemory_factory.CTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
          'ctest', '--timeout', '120', '-VV', '-S',
          '../dynamorio/suite/runsuite.cmake'],
        'descriptionDone': 'pre-commit suite',
        'name': 'pre-commit suite',
      }
    ),
  'dynamorio_precommit': (main.factory.drmemory_factory.CTest,
      {
        'command': ['ctest', '--timeout', '120', '-VV', '-S',
          '../dynamorio/suite/runsuite.cmake'],
        'name': 'pre-commit suite',
        'descriptionDone': 'pre-commit suite',
      }
    ),
  'drmemory_ctest': (main.factory.drmemory_factory.CTest,
      {
        'command': ['ctest', '--timeout', '60', '-VV', '-S'],
        'name': 'Dr. Memory ctest',
        'descriptionDone': 'runsuite',
      }
    ),
  'upload_dynamorio_docs': (buildbot.steps.transfer.DirectoryUpload,
      {
        'blocksize': 16384,
        'maindest': 'public_html/dr_docs',
        'subordinatesrc': 'install/docs/html',
        'workdir': 'build',
      }
    ),
  'get_dynamorio_buildnumber': (buildbot.steps.shell.SetProperty,
      {
        'description': 'get package build number',
        'name': 'get package build number',
      }
    ),
  'package_dynamorio': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['ctest', '-VV', '-S'],
        'description': 'Package DynamoRIO',
        'name': 'Package DynamoRIO',
      }
    ),
  'package_drmemory': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['ctest', '-VV', '-S'],
        'description': 'Package Dr. Memory',
        'name': 'Package Dr. Memory',
      }
    ),
  'find_dynamorio_package': (buildbot.steps.shell.SetProperty,
      {
        'description': 'find package file',
        'name': 'find package file',
        'strip': True,
      }
    ),
  'upload_dynamorio_package': (buildbot.steps.transfer.FileUpload,
      {
        'blocksize': 16384,
        'name': 'Upload DR package',
      }
    ),
  'upload_drmemory_package': (buildbot.steps.transfer.FileUpload,
      {
        'blocksize': 16384,
        'name': 'upload revision build',
      }
    ),
  'win_package_dynamorio': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
          'ctest', '-VV', '-S'],
        'description': 'Package DynamoRIO',
        'name': 'Package DynamoRIO',
      }
    ),
  'dartino': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python', 'tools/bots/dartino.py'],
        'description': 'annotated_steps',
        'env': {'BUILDBOT_ANNOTATED_STEPS_RUN': '1'},
        'name': 'annotated_steps',
        'workdir': 'build/sdk',
      }
    ),
  'dart_taskkill': (buildbot.steps.shell.ShellCommand,
      {
        'command': 'python third_party/dart/tools/task_kill.py'+\
            ' --kill_browsers=True',
        'name': 'Taskkill',
        'workdir': 'build/sdk',
      }
    ),
  'trigger': (buildbot.steps.trigger.Trigger,
      {
        # nothing here for now
      }
    ),
  'win_dart_taskkill': (buildbot.steps.shell.ShellCommand,
      {
        'command': 'python third_party/dart/tools/task_kill.py'+\
            ' --kill_browsers=True',
        'name': 'Taskkill',
        'workdir': 'build\\sdk',
      }
    ),
  'win_dartino': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate', 'tools/bots/dartino.py'],
        'description': 'annotated_steps',
        'env': {'BUILDBOT_ANNOTATED_STEPS_RUN': '1'},
        'name': 'annotated_steps',
        'workdir': 'build\\sdk',
      }
    ),
  'drmemory_pack_results': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['7z', 'a', '-xr!*.pdb', 'testlogs.7z'],
        'description': 'pack results',
        'name': 'Pack test results',
      }
    ),
  'drmemory_pack_results_win': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    '7z', 'a', '-xr!*.pdb', 'testlogs.7z'],
        'description': 'pack results',
        'name': 'Pack test results',
      }
    ),
  'upload_drmemory_test_logs': (buildbot.steps.transfer.FileUpload,
      {
        'blocksize': 16384,
        'name': 'Upload test logs to the main',
        'subordinatesrc': 'testlogs.7z',
      }
    ),
  'win_drmemory_ctest': (main.factory.drmemory_factory.CTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'ctest',
                    '--timeout',
                    '60',
                    '-VV',
                    '-S',
                   ],
        'descriptionDone': 'runsuite',
        'name': 'Dr. Memory ctest',
      }
    ),
  'config_release_dynamorio': (buildbot.steps.shell.Configure,
      {
        'command': ['cmake', '..', '-DDEBUG=OFF'],
        'name': 'Configure release DynamoRIO',
        'workdir': 'dynamorio/build',
      }
    ),
  'compile_release_dynamorio': (buildbot.steps.shell.Compile,
      {
        'command': ['make', '-j5'],
        'name': 'Compile release DynamoRIO',
        'workdir': 'dynamorio/build',
      }
    ),
  'dont_follow_python': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['bin64/drconfig', '-reg', 'python', '-norun', '-v'],
        'description': "don't follow python",
        'descriptionDone': "don't follow python",
        'workdir': 'dynamorio/build',
      }
    ),
  'drmemory_tests': (buildbot.steps.shell.Test,
      {
        'command': [ 'xvfb-run',
          '-a',
          '../dynamorio/build/bin64/drrun',
          '-stderr_mask',
          '12',
          '--'],
        'env': { 'CHROME_DEVEL_SANDBOX': '/opt/chromium/chrome_sandbox' },
      }
    ),
  'checkout_tsan': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['svn', 'checkout', '--force',
          'http://data-race-test.googlecode.com/svn/trunk/', '../tsan'],
        'description': 'checkout tsan tests',
        'name': 'Checkout TSan tests',
      }
    ),
  'build_tsan_tests': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'make',
                    '-C',
                    '../tsan/unittest'
          ],
        'description': 'build tsan tests',
        'descriptionDone': 'build tsan tests',
        'env': {'CYGWIN': 'nodosfilewarning'},
        'name': 'Build TSan tests',
      }
    ),
  'drmemory_tsan_test_dbg': (main.factory.drmemory_factory.DrMemoryTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'build_drmemory-dbg-32\\bin\\drmemory',
                    '-dr_ops',
                    '-msgbox_mask 0 -stderr_mask 15',
                    '-results_to_stderr',
                    '-batch',
                    '-suppress',
                    '..\\drmemory\\tests\\app_suite\\default-suppressions.txt',
                    '--']
      }
    ),
  'drmemory_tsan_test_rel': (main.factory.drmemory_factory.DrMemoryTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'build_drmemory-rel-32\\bin\\drmemory',
                    '-dr_ops',
                    '-msgbox_mask 0 -stderr_mask 15',
                    '-results_to_stderr',
                    '-batch',
                    '-suppress',
                    '..\\drmemory\\tests\\app_suite\\default-suppressions.txt',
                    '--']
      }
    ),
  'drmemory_tsan_test_dbg_light': (main.factory.drmemory_factory.DrMemoryTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'build_drmemory-dbg-32\\bin\\drmemory',
                    '-dr_ops',
                    '-msgbox_mask 0 -stderr_mask 15',
                    '-results_to_stderr',
                    '-batch',
                    '-suppress',
                    '..\\drmemory\\tests\\app_suite\\default-suppressions.txt',
                    '-light',
                    '--']
      }
    ),
  'drmemory_tsan_test_rel_light': (main.factory.drmemory_factory.DrMemoryTest,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
                    'build_drmemory-rel-32\\bin\\drmemory',
                    '-dr_ops',
                    '-msgbox_mask 0 -stderr_mask 15',
                    '-results_to_stderr',
                    '-batch',
                    '-suppress',
                    '..\\drmemory\\tests\\app_suite\\default-suppressions.txt',
                    '-light',
                    '--']
      }
    ),
  'drmemory_win7_tests': (buildbot.steps.shell.Test,
      {
        'command': ['..\\..\\win7-cr-builder\\build\\src\\tools\\valgrind'
          '\\chrome_tests.bat', '-t'],
      }
    ),
  'drmemory_win8_tests': (buildbot.steps.shell.Test,
      {
        'command': ['..\\..\\win8-cr-builder\\build\\src\\tools\\valgrind'
          '\\chrome_tests.bat', '-t'],
      }
    ),
  'drmemory_unpack_build': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['drm-sfx', '-ounpacked', '-y'],
        'description': 'unpack the build',
        'name': 'Unpack the build',
      }
    ),
  'drmemory_get_revision': (buildbot.steps.shell.SetProperty,
      {
        'command': ['unpacked\\bin\\drmemory', '-version'],
        'description': 'get revision',
        'descriptionDone': 'get revision',
        'name': 'Get the revision number',
      }
    ),
  'drmemory_download_build': (buildbot.steps.transfer.FileDownload,
      {
        'blocksize': 16384,
        'mainsrc': 'public_html/builds/drmemory-windows-latest-sfx.exe',
        'name': 'Download the latest build',
        'subordinatedest': 'drm-sfx.exe',
      }
    ),
  'drmemory_prepare_pack_win': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['del', 'testlogs.7z'],
        'description': 'cleanup',
        'name': 'Prepare to pack test results',
      }
    ),
  'drmemory_prepare_pack': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['rm', '-f', 'testlogs.7z'],
        'description': 'cleanup',
        'name': 'Prepare to pack test results',
      }
    ),
  'package_drmemory_win': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
          'ctest', '-VV', '-S'],
        'description': 'Package Dr. Memory',
        'name': 'Package Dr. Memory',
      }
    ),
  'drmemory_find_package_basename': (buildbot.steps.shell.SetProperty,
      {
        'command': 'dir /B DrMemory-Windows-*%(pkg_buildnum)s.zip',
        'description': 'find package basename',
        'name': 'find package basename',
      }
    ),
  'delete_prior_sfx_archive': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['del'],
        'description': 'delete prior sfx archive',
        'name': 'delete prior sfx archive',
      }
    ),
  'drmemory_create_sfx_archive': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['E:\\b\\build\\scripts\\subordinate\\drmemory\\build_env.bat',
          '7z', 'a', '-sfx'],
        'description': 'create sfx archive',
        'name': 'create sfx archive',
      }
    ),
  'upload_drmemory_latest': (buildbot.steps.transfer.FileUpload,
      {
        'blocksize': 16384,
        'maindest': 'public_html/builds/drmemory-windows-latest-sfx.exe',
        'name': 'upload latest build',
      }
    ),
  'start_crash_handler': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\chromium\\run_crash_handler.py',
          '--target'],
        'description': 'running start_crash_handler',
        'descriptionDone': 'start_crash_handler',
        'name': 'start_crash_handler',
      }
    ),
  'process_dumps': (main.log_parser.retcode_command.ReturnCodeCommand,
      {
        'command': ['python_subordinate',
                    '..\\..\\..\\scripts\\subordinate\\process_dumps.py',
                    '--target'],
        'description': 'running process_dumps',
        'descriptionDone': 'process_dumps',
        'name': 'process_dumps',
      }
    ),
  'extract_build': (main.log_parser.retcode_command.ReturnCodeCommand,
      {
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\extract_build.py',
          '--target'],
        'description': 'running extract_build',
        'descriptionDone': 'extract_build',
        'name': 'extract_build',
      }
    ),
  'runbuild_win': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate', '..\\..\\..\\scripts\\subordinate\\runbuild.py',
          '--annotate'],
        'description': 'buildrunner_tests',
        'name': 'buildrunner_tests',
      }
    ),
  'runbuild': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python', '../../../scripts/subordinate/runbuild.py',
          '--annotate'],
        'description': 'buildrunner_tests',
        'name': 'buildrunner_tests',
      }
    ),
  'zip_build_win': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate', '..\\..\\..\\scripts\\subordinate\\zip_build.py',
          '--target'],
        'description': 'packaging build',
        'descriptionDone': 'packaged build',
        'name': 'package_build',
      }
    ),
  'test_mini_installer_win': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\chromium' +\
          '\\test_mini_installer_wrapper.py', '--target'],
        'description': 'running test_installer',
        'descriptionDone': 'test_installer',
        'name': 'test_installer',
      }
    ),
  'update_clang': (buildbot.steps.shell.ShellCommand,
      {
        'command': ['python', 'src/tools/clang/scripts/update.py'],
        'description': 'Updating and building clang and plugins',
        'descriptionDone': 'clang updated',
        'env': { 'LLVM_URL': 'http://llvm.org/svn/llvm-project' },
        'name': 'update_clang',
      }
    ),
  'nacl_integration': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate',
          'src\\chrome\\test\\nacl_test_injection\\' +\
              'buildbot_nacl_integration.py'],
        'description': 'running nacl_integration',
        'descriptionDone': 'nacl_integration',
        'name': 'nacl_integration',
      }
    ),
  'nacl_sdk_buildbot_run': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python',
          '../../../scripts/subordinate/chromium/nacl_sdk_buildbot_run.py'],
        'description': 'annotated_steps',
        'name': 'annotated_steps',
      }
    ),
  'gclient_clobber': (main.chromium_step.GClient,
      {
        'mode': 'clobber',
      }
    ),
  'nacl_sdk_buildbot_run_win': (main.chromium_step.AnnotatedCommand,
      {
        'command': ['python_subordinate',
          '..\\..\\..\\scripts\\subordinate\\chromium\\nacl_sdk_buildbot_run.py'],
        'description': 'annotated_steps',
        'name': 'annotated_steps',
      }
    ),
}

# Conversion functions for specific step types.

# Convert special arguments to recipes.
def convert_arguments(args):
  arg_lookup = {
      '--build-number': ("'%s', %s", '--build-number',
                         'api.properties["buildnumber"]'),
      '--builder-name': ("'%s', %s", '--builder-name',
                         'api.properties["buildername"]'),
      '../../../scripts/subordinate/chromium/layout_test_wrapper.py': (
        '%s', 'api.path["build"].join("scripts", "subordinate", "chromium", '+\
            '"layout_test_wrapper.py")'
        )
  }
  fmtstr = ''
  fmtlist = []
  for arg in args:
    if isinstance(arg, str):
      if arg in arg_lookup:
        fmtstr = fmtstr + ', ' + arg_lookup[arg][0]
        fmtlist = fmtlist + list(arg_lookup[arg][1:])
      else:
        fmtstr = fmtstr + ", '%s'"
        fmtlist = fmtlist + [arg]
    if isinstance(arg, buildbot.process.properties.WithProperties):
      if arg.fmtstring == '--build-properties=%s':
        fmtstr = fmtstr + ', ' + '"--build-properties=%%s" %% %s'
        fmtlist = fmtlist +\
            ["api.json.dumps(build_properties, separators=(',', ':'))"]

  return fmtstr[2:] % tuple(fmtlist)

# Helpers for converting trigger steps
def get_builders_from_triggerable(c, sched_name):
  for sched in c['schedulers']:
    if sched.name == sched_name:
      return sched.builderNames
  raise Exception('Triggerable %s not found' % sched_name)

def builders_to_triggerspec(builder_list):
  return [{'builder_name': x} for x in builder_list]

def sched_to_triggerspec(sched_name):
  return builders_to_triggerspec(\
      get_builders_from_triggerable(_GLOBAL_BUILDMASTER_CONFIG, sched_name))

# Converter for use when step a step is unmatched or multiply matched.
def dump_converter(step, comment="dump converter"):
  rc = recipe_chunk()
  rc.steps.append('# %s' % comment)
  rc.steps.append(pprint.pformat(step, indent=2))
  return rc

def null_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# %s step; null converted' % step[1].get('name', 'unnamed'))
  return rc

def nacl_sdk_buildbot_run_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# annotated_steps step')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/json')
  rc.deps.add('recipe_engine/path')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  nsdk_command = 'api.path["build"].join("scripts", "subordinate", "chromium", '+\
      '"nacl_sdk_buildbot_run.py")'
  fmtstr = 'api.python("annotated_steps", %s, args=[%s, \'%s\'],' +\
      ' allow_subannotations=True)'
  rc.steps.append(fmtstr % (nsdk_command, build_properties,
                            step[1]['command'][3]))
  return rc

def test_mini_installer_win_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  rc.steps.append('# test mini installer wrapper step')
  rc.steps.append('api.python("test installer", ' +\
      'api.path["build"].join("scripts", "subordinate", "chromium", '+\
      '"test_mini_installer_wrapper.py"), args=[' +\
      '"--target", "%s"])' % step[1]['command'][3])
  return rc

def zip_build_win_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/json')
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  rc.steps.append('# zip_build step')
  rc.steps.append('step_result = api.python("zip build", ' +\
      'api.path["build"].join("scripts", "subordinate", "zip_build.py"), ' +\
      'args=["--json-urls", api.json.output(), '
      '"--target", "%s", ' % step[1]['command'][3] +\
      repr(step[1]['command'][4:6])[1:-1] +\
      ', %s, ' % build_properties +\
      '\'%s\'])' % step[1]['command'][7])
  rc.steps.append('if "storage_url" in step_result.json.output:')
  rc.steps.append(['step_result.presentation.links["download"] = '
    'step_result.json.output["storage_url"]'])
  rc.steps.append('build_properties["build_archive_url"] = '
      'step_result.json.output["zip_url"]')
  return rc

def runbuild_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/json')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  rc.steps.append('# runbuild step')
  rc.steps.append('api.python("runbuild", ' +\
      'api.path["build"].join("scripts", "subordinate", "runbuild.py"), args=[' +\
      '"--annotate", ' +\
      '%s, ' % build_properties +\
      '\'%s\'])' % step[1]['command'][4])
  return rc

def runbuild_win_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/json')
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  rc.steps.append('# runbuild step')
  rc.steps.append('api.python("runbuild", ' +\
      'api.path["build"].join("scripts", "subordinate", "runbuild.py"), ' +\
      'args=["--annotate", ' +\
      '%s, ' % build_properties +\
      '\'%s\'])' % step[1]['command'][4])
  return rc

def extract_build_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/json')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  rc.steps.append('# extract build step')
  rc.steps.append('api.python("extract build", ' +\
      'api.path["build"].join("scripts", "subordinate", "extract_build.py"), ' +\
      'args=["--target", "%s", ' % step[1]['command'][3] +\
      '"--build-archive-url", ' +\
      'build_properties["parent_build_archive_url"], ' +\
      '%s])' % build_properties)
  return rc

def dynamorio_unpack_tools_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  fmtstr = 'api.step("%s", %s, env=%s, cwd=%s)'
  cmdstr = 'api.path["subordinate_build"].join(' +\
      repr(step[1]['workdir'].split('/') + ['unpack.bat'])[1:-1] + ')'
  cwd = 'api.path["subordinate_build"]'
  if step[1].get('workdir', ''):
    cwd += '.join(%s)' % repr(step[1]['workdir'].split('/'))[1:-1]
  env = "{}"
  if step[1].get('env', {}):
    env = repr(step[1]['env'])
  rc.steps.append('# %s step; generic ShellCommand converted' % step[1]['name'])
  rc.steps.append(fmtstr % (step[1]['name'], cmdstr, env,
    cwd))
  return rc

def process_dumps_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  rc.steps.append('# process dumps step')
  rc.steps.append('api.python("process dumps", '
      'api.path["build"].join("scripts", "subordinate", "process_dumps.py"), '
      'args=["--target", "%s"])' % step[1]['command'][3])
  return rc

def start_crash_handler_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  rc.steps.append('# start crash handler step')
  rc.steps.append('api.python("start crash handler", '
      'api.path["build"].join("scripts", "subordinate", "chromium", '
      '"run_crash_handler.py"), '
      'args=["--target", "%s"])' % step[1]['command'][3])
  return rc

def upload_drmemory_latest_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('gsutil')
  rc.steps.append('# upload latest build step')
  local_file = 'drmemory-windows-latest-sfx.exe'
  bucket = 'chromium-drmemory-builds'
  remote_dir = '""'
  rc.steps.append('api.step("copy locally", ["copy", basename + "-sfx.exe",'
      ' "drmemory-windows-latest-sfx.exe"], cwd=api.path["subordinate_build"])')
  rc.steps.append('api.gsutil.upload("%s", "%s", %s,'
      ' cwd=api.path["subordinate_build"])' % (local_file, bucket,
    remote_dir))
  return rc

def drmemory_create_sfx_archive_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# Create sfx archive step')
  build_env = 'api.path["build"].join("scripts", "subordinate", "drmemory",'+\
      '"build_env.bat")'
  env = ('{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '
      '"bot_tools")}')
  archive_name = 'basename + "-sfx.exe"'
  archive_source = ('"build_drmemory-debug-32\\\\_CPack_Packages\\\\Windows\\\\'
      'ZIP\\\\" + basename + "\\\\*"')
  rc.steps.append('api.step("create sfx archive", [%s, "7z", "a"' % build_env +\
      ', "-sfx", %s, %s], cwd=api.path["subordinate_build"], env=%s)' % (archive_name,
        archive_source, env))
  return rc

def drmemory_find_package_basename_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/raw_io')
  rc.steps.append('# Find package basename step')
  rc.steps.append('step_result = api.step("Find package basename", ["dir",'
      ' "/B", '
      '"DrMemory-Windows-*0x" + build_properties["got_revision"][:7] + '
      '".zip"], stdout=api.raw_io.output(), cwd=api.path["subordinate_build"])')
  rc.steps.append('basename = step_result.stdout[:-4]')
  return rc

def delete_prior_sfx_archive_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# Delete prior sfx archive step')
  rc.steps.append('api.step("Delete prior sfx archive", '
      '["del", basename + "-sfx.exe"], cwd=api.path["subordinate_build"])')
  return rc

def package_drmemory_win_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  build_env = 'api.path["build"].join("scripts", "subordinate", "drmemory",'+\
      '"build_env.bat")'
  env = ('{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '
      '"bot_tools")}')
  confstr = ('str(api.path["checkout"].join("package.cmake")) + ",build=0x"'
      ' + build_properties["got_revision"][:7] + ";drmem_only"')
  rc.steps.append('# Package dynamorio step')
  rc.steps.append('api.step("Package Dr. Memory", [%s, %s, %s],' % (build_env,
        repr(step[1]['command'][1:4])[1:-1], confstr) +\
      'env=%s, cwd=api.path["subordinate_build"])' % env)
  return rc

def drmemory_get_revision_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/raw_io')
  rc.steps.append('# Dr. Memory get revision step')
  rc.steps.append('step_result = api.step("Get the revision number", '
      '%s, stdout=api.raw_io.output())' % repr(step[1]['command']))
  rc.steps.append('build_properties["got_revision"] = '
      'step_result.stdout.split()[3].split(".")[2]')
  return rc

def drmemory_download_build_converter(step):
  rc = recipe_chunk()
  rc.deps.add('gsutil')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# Download build step')
  rc.steps.append('api.gsutil.download("chromium-drmemory-builds", '
      '"drmemory-windows-latest-sfx.exe", "drm-sfx.exe", '
      'cwd=api.path["subordinate_build"])')
  return rc

def drmemory_tsan_test_light_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# Dr. Memory TSan test step')
  env = '{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '+\
      '"bot_tools")}'
  rc.steps.append('api.step("%s", [' % step[1]['name'] +\
      'api.path["build"].join("scripts", "subordinate", "drmemory", ' +\
      '"build_env.bat"), '+\
      repr(step[1]['command'][1:7])[1:-1] +\
      ', api.path["checkout"].join("tests", "app_suite", '+\
      '"default-suppressions.txt"), "-light", "--", ' +\
      'api.path["subordinate_build"].join("tsan", '+\
      '%s), ' % repr(step[1]['command'][10].split('\\')[2:])[1:-1] +\
      '%s], ' % repr(step[1]['command'][-2:])[1:-1] +\
      'env=%s)' % env)
  return rc

def drmemory_tsan_test_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/step')
  rc.steps.append('# Dr. Memory TSan test step')
  env = '{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '+\
      '"bot_tools")}'
  rc.steps.append('api.step("%s", [' % step[1]['name'] +\
      'api.path["build"].join("scripts", "subordinate", "drmemory", ' +\
      '"build_env.bat"), '+\
      repr(step[1]['command'][1:7])[1:-1] +\
      ', api.path["checkout"].join("tests", "app_suite", '+\
      '"default-suppressions.txt"), "--", ' +\
      'api.path["subordinate_build"].join("tsan", '+\
      '%s), ' % repr(step[1]['command'][9].split('\\')[2:])[1:-1] +\
      '%s], ' % repr(step[1]['command'][-2:])[1:-1] +\
      'env=%s)' % env)
  return rc

def build_tsan_tests_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  env = '{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '+\
      '"bot_tools"), "CYGWIN": "nodosfilewarning"}'
  rc.steps.append("# Build TSan tests step")
  rc.steps.append('api.step("Build TSan Tests", ' +\
      '[%s, ' % repr(step[1]['command'][:-1])[1:-1] +\
      '%s], ' % 'api.path["subordinate_build"].join("tsan", "unittest")' +\
      "env=%s)" % env)
  return rc

def checkout_tsan_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# Checkout TSan tests step')
  rc.steps.append('api.step("Checkout TSan tests",' +\
      ' [%s, ' % repr(step[1]['command'][:-1])[1:-1] +\
      'api.path["subordinate_build"].join("tsan")])')
  return rc

def drmemory_tests_converter(step):
  rc = recipe_chunk()
  env = "{}"
  if step[1].get('env', {}):
    env = repr(step[1]['env'])
  rc.steps.append("# drmemory test step")
  rc.steps.append('api.step("%s", [%s, '%(step[1]['name'],
                                          repr(step[1]['command'][:2])[1:-1])+\
      'api.path["checkout"].join("build",' +\
      '"bin64", "drrun"), %s], ' % repr(step[1]['command'][3:])[1:-1] +\
      'env=%s, cwd=api.path["checkout"])' % env)
  return rc

def config_release_dynamorio_converter(step):
  rc = recipe_chunk()
  rc.deps.add('file')
  rc.deps.add('recipe_engine/path')
  rc.steps.append("# Make the build directory step")
  rc.steps.append('api.file.makedirs("makedirs", api.path["subordinate_build"].'
      'join("dynamorio"))')
  rc.steps.append('api.file.makedirs("makedirs", api.path["subordinate_build"].'
      'join("dynamorio", "build"))')
  rc = rc + generic_shellcommand_converter(step)
  return rc

def win_drmemory_ctest_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# windows Dr. Memory ctest step')
  script = ('api.path["build"].join("scripts", "subordinate", "drmemory",'
      ' "build_env.bat")')
  confstr = ('str(api.path["checkout"].join("tests", "runsuite.cmake")) + '
      '",drmemory_only;long;build=" + str(build_properties["buildnumber"])')
  rc.steps.append('api.step("Dr. Memory ctest", [%s, %s, %s])' % (script,
    repr(step[1]['command'][1:6])[1:-1], confstr))
  return rc

def drmemory_pack_results_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.steps.append("# Pack test results step")
  zipname = ('"testlogs_r" + build_properties["got_revision"] + "_b" +'
  ' str(build_properties["buildnumber"]) + ".7z"')
  rc.steps.append('api.step("Pack test results", '
      '[%s, %s, %s])' % (repr(step[1]['command'][:3])[1:-1], zipname,
        repr(step[1]['command'][4:])[1:-1]))
  return rc

def drmemory_pack_results_win_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append("# Pack test results step")
  build_env = 'api.path["build"].join("scripts", "subordinate", "drmemory",'+\
      '"build_env.bat")'
  env = ('{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '
      '"bot_tools")}')
  zipname = ('"testlogs_r" + build_properties["got_revision"] + "_b" +'
  ' str(build_properties["buildnumber"]) + ".7z"')
  rc.steps.append('api.step("Pack test results", '
      '[%s, %s, %s, %s], env=%s)' % (build_env,
        repr(step[1]['command'][1:4])[1:-1], zipname,
        repr(step[1]['command'][5:])[1:-1], env))
  return rc

def drmemory_ctest_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# Dr. Memory ctest step')
  rc.steps.append('api.step("Dr. Memory ctest", ["ctest", "--timeout", "60", '
      '"-VV", "-S", str(api.path["checkout"].join("tests", "runsuite.cmake"))'
      ' + ",drmemory_only;long;build=0x"'
      ' + build_properties["got_revision"][:7]])')
  return rc

def upload_drmemory_package_converter(step):
  rc = recipe_chunk()
  rc.deps.add('gsutil')
  rc.steps.append('# upload drmemory build step')
  local_file = '"DrMemory-TODO-*" + build_properties["got_revision"][:7]'+\
      ' + ".TODO"'
  bucket = 'chromium-drmemory-builds'
  remote_dir = '"builds/"'
  rc.steps.append('api.gsutil.upload(%s, "%s", %s)' % (local_file, bucket,
    remote_dir))
  return rc

def upload_drmemory_test_logs_converter(step):
  rc = recipe_chunk()
  rc.deps.add('gsutil')
  rc.steps.append('# upload drmemory test logs step')
  zipname = ('"testlogs_r" + build_properties["got_revision"] + "_b" +'
  ' str(api.properties["buildnumber"]) + ".7z"')
  bucket = 'chromium-drmemory-builds'
  remote_dir = '"testlogs/from_%s" % api.properties["buildername"]'
  rc.steps.append('api.gsutil.upload(%s, "%s", %s)' % (zipname, bucket,
    remote_dir))
  return rc

def package_drmemory_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  rc.steps.append('# Package DrMemory step')
  confstr = 'str(api.path["checkout"].join("package.cmake")) + '+\
      '",build=0x" + build_properties["got_revision"][:7] + ";drmem_only"'
  rc.steps.append('api.step("Package Dr. Memory", ["ctest", "-VV", "-S", %s])'%\
      confstr)
  return rc

def checkout_drmemory_converter(step):
  rc = recipe_chunk()
  rc.deps.add('depot_tools/bot_update')
  rc.deps.add('depot_tools/gclient')
  rc.steps.append('# checkout DrMemory step')
  rc.steps.append('src_cfg = api.gclient.make_config(GIT_MODE=True)')
  rc.steps.append('soln = src_cfg.solutions.add()')
  rc.steps.append('soln.name = "%s"' % 'drmemory')
  rc.steps.append('soln.url = "%s"' % step[1]['repourl'])
  rc.steps.append('soln.custom_deps = {"drmemory/dynamorio":'
      ' "https://github.com/DynamoRIO/dynamorio.git", "tools/buildbot": '
      '"https://github.com/DynamoRIO/buildbot.git"}')
  rc.steps.append('api.gclient.c = src_cfg')
  rc.steps.append('result = api.bot_update.ensure_checkout(force=True)')
  rc.steps.append(
      'build_properties.update(result.json.output.get("properties", {}))')
  return rc

def trigger_converter(step):
  rc = recipe_chunk()
  rc.deps.add('trigger')
  rc.deps.add('recipe_engine/properties')
  prop_set = step[1].get('set_properties', {})
  propstr = '{'
  for prop in prop_set.keys():
    if isinstance(prop_set[prop], str):
      propstr += '"%s": "%s", ' % (prop, prop_set[prop])
    elif isinstance(prop_set[prop],
        buildbot.process.properties.WithProperties):
      propstr += '"%s": build_properties.get("%s", ""), ' % (prop,
          prop_set[prop].fmtstring[2:-4])
  propstr += '}'
  trigger_spec = []
  for sched in step[1]['schedulerNames']:
    trigger_spec.extend(sched_to_triggerspec(sched))
  rc.steps.append('# trigger step')
  rc.steps.append('trigger_spec = [')
  triggers = []
  for trigger in trigger_spec:
    triggers.append(repr(trigger)[:-1] + ', "properties": %s},' % propstr)
  rc.steps.append(triggers)
  rc.steps.append(']')
  rc.steps.append('api.trigger(*trigger_spec)')
  return rc

def dart_taskkill_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  env = {}
  if 'BUILDBOT_JAVA_HOME' in step[1]['env']:
    env = "{'BUILDBOT_JAVA_HOME': api.path['checkout'].join('third_party', "+\
        "'java', 'linux', 'j2sdk')}"
  rc.steps.append("# taskkill step")
  rc.steps.append('api.python("Taskkill", '+\
      'api.path["checkout"].join("third_party", "dart", "tools", '+\
      '"task_kill.py"), args=["--kill_browsers=True"], '+\
      'env=%s, ' % env +\
      'cwd=api.path["checkout"])')
  return rc

def win_dart_taskkill_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.steps.append("# taskkill step")
  rc.steps.append('api.python("Taskkill", '+\
      'api.path["checkout"].join("third_party", "dart", "tools", '+\
      '"task_kill.py"), args=["--kill_browsers=True"], '+\
      'cwd=api.path["checkout"])')
  return rc

def dartino_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  rc.steps.append("# dartino annotated steps step")
  env_add = ', "BUILDBOT_BUILDERNAME": api.properties["buildername"]'
  rc.steps.append('api.python("annotated steps", '+\
      'api.path["checkout"].join("tools", "bots", "dartino.py"), '+\
      'allow_subannotations=True, env={%s%s}, ' % (repr(step[1]['env'])[1:-1],
        env_add) +\
      'cwd=api.path["checkout"])')
  return rc

def win_dartino_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/python')
  rc.steps.append("# dartino annotated steps step")
  env_add = ', "BUILDBOT_BUILDERNAME": api.properties["buildername"]'
  rc.steps.append('api.python("annotated steps", '+\
      'api.path["checkout"].join("tools", "bots", "dartino.py"), '+\
      'allow_subannotations=True, env={%s%s}, ' % (repr(step[1]['env'])[1:-1],
        env_add) +\
      'cwd=api.path["checkout"])')
  return rc

def win_package_dynamorio_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  rc.steps.append('# Package DynamoRIO step')
  build_env_bat = 'api.path["build"].join("scripts", "subordinate", "drmemory", '+\
      '"build_env.bat")'
  confstr = 'str(api.path["checkout"].join("make", "package.cmake")) + '+\
      '",build=0x" + str(api.properties["revision"])[:7]'
  env = '{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '+\
      '"bot_tools")}'
  rc.steps.append('api.step("Package DynamoRIO", '+\
      '[%s, "ctest", "-VV", "-S", %s], env=%s)' % (build_env_bat, confstr, env))
  return rc

def dynamorio_nightly_suite_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# dynamorio nightly suite step')
  rc.steps.append('api.step("nightly suite", ["ctest", "--timeout", "120", '+\
      '"-VV", "-S", str(api.path["checkout"].join("suite", "runsuite.cmake"))'+\
      ' + ",nightly;long;site=X64.Linux.VS2010.BuildBot"])')
  return rc

def find_dynamorio_package_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# find package file step; no longer necessary')
  return rc

def upload_dynamorio_package_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/properties')
  rc.deps.add('gsutil')
  rc.steps.append('# upload dynamorio package')
  local_file = '"DynamoRIO-TODO-*" + build_properties["got_revision"][:7]'+\
      ' + ".TODO"'
  bucket = 'chromium-dynamorio'
  remote_dir = '"builds/"'
  rc.steps.append('api.gsutil.upload(%s, "%s", %s)' % (local_file, bucket,
    remote_dir))
  return rc

def package_dynamorio_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  rc.steps.append('# Package DynamoRIO step')
  confstr = 'str(api.path["checkout"].join("make", "package.cmake")) + '+\
      '",build=0x" + build_properties["revision"][:7]'
  rc.steps.append('api.step("Package DynamoRIO", ["ctest", "-VV", "-S", %s])' %\
      confstr)
  return rc

def get_dynamorio_buildnumber_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# get buildnumber step; no longer needed')
  return rc

def upload_dynamorio_docs_converter(step):
  rc = recipe_chunk()
  rc.deps.add('gsutil')
  rc.deps.add('recipe_engine/path')
  local_file = 'api.path["subordinate_build"].join("install", "docs", "html")'
  bucket = '"chromium-dynamorio"'
  remote_dir = '"dr_docs/"'
  args = ['-r', '-m']
  rc.steps.append("# upload dynamorio docs step")
  rc.steps.append('api.gsutil.upload(%s, %s, %s, "%s")' % (local_file,
    bucket, remote_dir, repr(args)))
  return rc

def dynamorio_precommit_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# pre-commit suite step')
  command = repr(step[1]['command'][:-1])[1:-1]
  cmake_file = 'api.path["checkout"].join("suite", "runsuite.cmake")'
  cwd = 'api.path["subordinate_build"]'
  rc.steps.append('api.step("pre-commit suite", '+\
      '[%s, %s], cwd=%s, ok_ret="all")' % (command, cmake_file, cwd))
  return rc

def win_dynamorio_precommit_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# build_env step')
  fmtstr = 'api.step("pre-commit suite", [%s, %s, %s],  env=%s, '+\
      'cwd=api.path["subordinate_build"])'
  command = 'api.path["build"].join("scripts", "subordinate", "drmemory", '+\
      '"build_env.bat")'
  args = step[1]['command'][1:-1]
  runsuite = 'api.path["checkout"].join("suite", "runsuite.cmake")'
  env = '{"BOTTOOLS": api.path["subordinate_build"].join("tools", "buildbot", '+\
      '"bot_tools")}'
  rc.steps.append(fmtstr % (command, repr(args)[1:-1], runsuite, env))
  return rc

def win_dynamorio_nightly_suite_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  rc.steps.append('# dynamorio win nightly suite step')
  fmtstr = 'api.step("%s", [%s, %s], env=%s, cwd=api.path["subordinate_build"])'
  env = '{"BOTTOOLS": '+\
      'api.path["subordinate_build"].join("tools", "buildbot", "bot_tools")}'
  command = 'api.path["build"].join("scripts", "subordinate", "drmemory", '+\
      '"build_env.bat")'
  step[1]['command'][-1] = step[1]['command'][-1][3:]
  command_args = repr(step[1]['command'][1:])[1:-1]
  rc.steps.append(fmtstr % (step[1]['name'], command, command_args, env))
  return rc

def checkout_dynamorio_converter(step):
  rc = recipe_chunk()
  rc.deps.add('depot_tools/bot_update')
  rc.deps.add('depot_tools/gclient')
  rc.steps.append('# checkout DynamiRIO step')
  rc.steps.append('src_cfg = api.gclient.make_config(GIT_MODE=True)')
  rc.steps.append('soln = src_cfg.solutions.add()')
  rc.steps.append('soln.name = "%s"' % 'dynamorio')
  rc.steps.append('soln.url = "%s"' % step[1]['repourl'])
  rc.steps.append('api.gclient.c = src_cfg')
  rc.steps.append('result = api.bot_update.ensure_checkout(force=True)')
  rc.steps.append(
      'build_properties.update(result.json.output.get("properties", {}))')
  return rc

def generic_shellcommand_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/step')
  fmtstr = 'api.step("%s", %s, env=%s, cwd=%s)'
  cwd = 'api.path["subordinate_build"]'
  if step[1].get('workdir', ''):
    cwd += '.join(%s)' % repr(step[1]['workdir'].split('/'))[1:-1]
  env = "{}"
  if step[1].get('env', {}):
    env = repr(step[1]['env'])
  rc.steps.append('# %s step; generic ShellCommand converted' % step[1]['name'])
  rc.steps.append(fmtstr % (step[1]['name'], repr(step[1]['command']), env,
    cwd))
  return rc

def runtest_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/json')
  rc.steps.append('# runtest step')
  if isinstance(step[1]['command'], main.optional_arguments.ListProperties):
    args = step[1]['command'].items[2:]
  else:
    args = step[1]['command'][2:]
  fmtstr = 'api.python("%s", api.path["build"].join("scripts", "subordinate",'+\
      '"runtest.py"), args=[%s])'
  rc.steps.append(fmtstr % (step[1]['name'],
    convert_arguments(args)))
  return rc

def win_runtest_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# runtest step')
  if not isinstance(step[1]['command'],  list):
    args = step[1]['command'].items[2:]
  else:
    args = step[1]['command'][2:]
  fmtstr = 'api.python("%s", '+\
      'api.path["build"].join("scripts", "subordinate", "runtest.py"), args=[%s])'
  rc.steps.append(fmtstr % (step[1]['name'],
    convert_arguments(args)))
  return rc

def win_taskkill_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# taskkill step')
  rc.steps.append('api.python("taskkill", api.path["build"].join("scripts", '+\
      '"subordinate", "kill_processes.py"))')
  return rc

def win_svnkill_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# svnkill step; not necessary in recipes')
  return rc

def cleanup_temp_converter(step):
  rc = recipe_chunk()
  rc.deps.add('chromium')
  rc.steps.append('# cleanup_temp step')
  rc.steps.append('api.chromium.cleanup_temp()')
  return rc

# Converter for update_scripts; the recipe engine does this automatically, so
# this converter is a no-op.
def update_scripts_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# update scripts step; implicitly run by recipe engine.')
  return rc

# NOTE: may require support for kwargs later.
def gclient_safe_revert_converter(step):
  rc = recipe_chunk()
  # This *should be* a no-op if run after bot_update; and bot_update has been
  # found to have been run on all builders encountered/attempted to be converted
  # so far.
  rc.steps.append('# gclient revert step; made unnecessary by bot_update')
  return rc

def gclient_update_converter(step):
  rc = recipe_chunk()
  # This *should be* a no-op if run after bot_update; and bot_update has been
  # found to have been run on all builders encountered/attempted to be converted
  # so far.
  rc.steps.append('# gclient update step; made unnecessary by bot_update')
  return rc

def bot_update_converter(step):
  rc = recipe_chunk()
  rc.deps = {'depot_tools/gclient', 'depot_tools/bot_update'}
  rc.steps.append('# bot_update step')
  # First, get the gclient config out of the command
  gclient_config = {}
  exec(step[1]['command'][4], gclient_config)
  # Write the gclient config to the recipe.
  rc.steps.append('src_cfg = api.gclient.make_config(GIT_MODE=True)')
  for soln in gclient_config['solutions']:
    rc.steps.append('soln = src_cfg.solutions.add()')
    rc.steps.append('soln.name = "%s"' % soln['name'])
    rc.steps.append('soln.url = "%s"' % soln['url'])
    if 'custom_deps' in soln:
      rc.steps.append('soln.custom_deps = %s' % repr(soln['custom_deps']))
    if 'custom_vars' in soln:
      rc.steps.append('soln.custom_vars = %s' % repr(soln['custom_vars']))
  if 'target_os' in gclient_config:
    rc.steps.append('src_cfg.target_os = set(%s)' %
        repr(gclient_config['target_os']))
  # If there's a revision mapping, get that as well.
  for rm in step[1]['command']:
    if isinstance(rm, basestring) and rm.startswith('--revision_mapping='):
      exec(rm[2:], gclient_config)
      break # There really shouldn't be more than a single revision mapping.
  if 'revision_mapping' in gclient_config:
    rc.steps.append('src_cfg.got_revision_mapping.update(%s)' %
        gclient_config['revision_mapping'])
  rc.steps.append('api.gclient.c = src_cfg')
  # Then, call bot_update on it.
  rc.steps.append('result = api.bot_update.ensure_checkout(force=True)')
  rc.steps.append(
      'build_properties.update(result.json.output.get("properties", {}))')
  # NOTE: wherever there is a gclient_runhooks steps after bot_update (which
  # *should* be everywhere), the '--gyp_env' argument need not be passed in;
  # that is why it is ignored here. (aneeshm)
  return rc

def bb_run_bot_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# subordinate_steps step')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/json')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  fmtstr = 'api.python("subordinate_steps", "%s", args=[%s, \'%s\'],' +\
      ' allow_subannotations=True)'
  rc.steps.append(fmtstr % (step[1]['command'][1], build_properties,
                            step[1]['command'][3]))
  return rc

def gclient_runhooks_wrapper_converter(step):
  rc = recipe_chunk()
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.steps.append('# gclient runhooks wrapper step')
  rc.steps.append('env = %s' % repr(step[1]['env']))
  rc.steps.append('api.python("gclient runhooks wrapper", ' +\
      'api.path["build"].join("scripts", "subordinate", "runhooks_wrapper.py"), '+\
      'env=env)')
  return rc

def chromedriver_buildbot_run_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# annotated_steps step')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/json')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  cdbbrun_command = 'api.path["build"].join("scripts", "subordinate", "chromium", '+\
      '"chromedriver_buildbot_run.py")'
  fmtstr = 'api.python("annotated_steps", %s, args=[%s, \'%s\'],' +\
      ' allow_subannotations=True)'
  rc.steps.append(fmtstr % (cdbbrun_command, build_properties,
                            step[1]['command'][3]))
  return rc

def win_chromedriver_buildbot_run_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# annotated_steps step')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/json')
  rc.deps.add('recipe_engine/path')
  build_properties = "'--build-properties=%s' % " +\
      "api.json.dumps(build_properties, separators=(',', ':'))"
  cdbbrun_command = 'api.path["build"].join("scripts", "subordinate", "chromium", '+\
      '"chromedriver_buildbot_run.py")'
  fmtstr = 'api.python("annotated_steps", %s, args=[%s, \'%s\'],' +\
      ' allow_subannotations=True)'
  rc.steps.append(fmtstr % (cdbbrun_command, build_properties,
                            step[1]['command'][3]))
  return rc

def compile_py_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# compile.py step')
  rc.deps.add('recipe_engine/python')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  fmtstr = 'api.python("compile", %s, args=args)'
  compile_command = 'api.path["build"].join("scripts", "subordinate", "compile.py")'
  args = [x for x in step[1]['command'].items[2:] if isinstance(x, str)]
  rc.steps.append('args = %s' % repr(args))
  for x in step[1]['command'].items[2:]:
    if isinstance(x, buildbot.process.properties.WithProperties) and\
       x.fmtstring == '%s' and\
       x.args == ('clobber:+--clobber',):
      rc.steps.append('if "clobber" in api.properties:')
      rc.steps.append(['args.append("--clobber")'])
  rc.steps.append(fmtstr % compile_command)
  return rc

def win_compile_py_converter(step):
  rc = recipe_chunk()
  rc.steps.append('# compile.py step')
  rc.deps.add('recipe_engine/path')
  rc.deps.add('recipe_engine/properties')
  fmtstr = 'api.python("compile", %s, args=args)'
  compile_command = 'api.path["build"].join("scripts", "subordinate", "compile.py")'
  args = [x for x in step[1]['command'].items[2:] if isinstance(x, str)]
  rc.steps.append('args = %s' % repr(args))
  for x in step[1]['command'].items[2:]:
    if isinstance(x, buildbot.process.properties.WithProperties) and\
       x.fmtstring == '%s' and\
       x.args == ('clobber:+--clobber',):
      rc.steps.append('if "clobber" in api.properties:')
      rc.steps.append(['args.append("--clobber")'])
  rc.steps.append(fmtstr % compile_command)
  return rc

_step_converters_map = {
    'cleanup_temp': cleanup_temp_converter,
    'win_cleanup_temp': cleanup_temp_converter,
    'update_scripts': update_scripts_converter,
    'gclient_safe_revert': gclient_safe_revert_converter,
    'win_gclient_safe_revert': gclient_safe_revert_converter,
    'gclient_update': gclient_update_converter,
    'bot_update': bot_update_converter,
    'win_bot_update': bot_update_converter,
    'bb_run_bot': bb_run_bot_converter,
    'gclient_runhooks_wrapper': gclient_runhooks_wrapper_converter,
    'win_gclient_runhooks_wrapper': gclient_runhooks_wrapper_converter,
    'chromedriver_buildbot_run': chromedriver_buildbot_run_converter,
    'win_chromedriver_buildbot_run': win_chromedriver_buildbot_run_converter,
    'compile_py': compile_py_converter,
    'win_compile_py': win_compile_py_converter,
    'win_svnkill': win_svnkill_converter,
    'win_update_scripts': update_scripts_converter,
    'win_taskkill': win_taskkill_converter,
    'runtest': runtest_converter,
    'runtest2': runtest_converter,
    'win_runtest': win_runtest_converter,
    'clear_tools': null_converter,
    'checkout_dynamorio': checkout_dynamorio_converter,
    'checkout_dynamorio_tools': null_converter,
    'dynamorio_unpack_tools': dynamorio_unpack_tools_converter,
    'win_dynamorio_nightly_suite': win_dynamorio_nightly_suite_converter,
    'win_dynamorio_precommit': win_dynamorio_precommit_converter,
    'dynamorio_precommit': dynamorio_precommit_converter,
    'upload_dynamorio_docs': upload_dynamorio_docs_converter,
    'get_dynamorio_buildnumber': get_dynamorio_buildnumber_converter,
    'package_dynamorio': package_dynamorio_converter,
    'find_dynamorio_package': find_dynamorio_package_converter,
    'upload_dynamorio_package': upload_dynamorio_package_converter,
    'dynamorio_nightly_suite': dynamorio_nightly_suite_converter,
    'win_package_dynamorio': win_package_dynamorio_converter,
    'dartino': dartino_converter,
    'dart_taskkill': dart_taskkill_converter,
    'trigger': trigger_converter,
    'win_dart_taskkill': win_dart_taskkill_converter,
    'win_dartino': win_dartino_converter,
    'package_drmemory': package_drmemory_converter,
    'checkout_drmemory': checkout_drmemory_converter,
    'upload_drmemory_package': upload_drmemory_package_converter,
    'drmemory_ctest': drmemory_ctest_converter,
    'drmemory_prepare_pack_win': null_converter,
    'drmemory_prepare_pack': null_converter,
    'drmemory_pack_results': drmemory_pack_results_converter,
    'upload_drmemory_test_logs': upload_drmemory_test_logs_converter,
    'win_drmemory_ctest': win_drmemory_ctest_converter,
    'config_release_dynamorio': config_release_dynamorio_converter,
    'compile_release_dynamorio': generic_shellcommand_converter,
    'dont_follow_python': generic_shellcommand_converter,
    'drmemory_tests': drmemory_tests_converter,
    'checkout_tsan': checkout_tsan_converter,
    'build_tsan_tests': build_tsan_tests_converter,
    'drmemory_tsan_test_dbg': drmemory_tsan_test_converter,
    'drmemory_tsan_test_rel': drmemory_tsan_test_converter,
    'drmemory_tsan_test_dbg_light': drmemory_tsan_test_light_converter,
    'drmemory_tsan_test_rel_light': drmemory_tsan_test_light_converter,
    'drmemory_pack_results_win': drmemory_pack_results_win_converter,
    'drmemory_download_build': drmemory_download_build_converter,
    'drmemory_unpack_build': generic_shellcommand_converter,
    'drmemory_win7_tests': generic_shellcommand_converter,
    'drmemory_win8_tests': generic_shellcommand_converter,
    'drmemory_get_revision': drmemory_get_revision_converter,
    'package_drmemory_win': package_drmemory_win_converter,
    'drmemory_find_package_basename': drmemory_find_package_basename_converter,
    'delete_prior_sfx_archive': delete_prior_sfx_archive_converter,
    'drmemory_create_sfx_archive': drmemory_create_sfx_archive_converter,
    'upload_drmemory_latest': upload_drmemory_latest_converter,
    'start_crash_handler': start_crash_handler_converter,
    'process_dumps': process_dumps_converter,
    'extract_build': extract_build_converter,
    'runbuild_win': runbuild_win_converter,
    'runbuild': runbuild_converter,
    'zip_build_win': zip_build_win_converter,
    'test_mini_installer_win': test_mini_installer_win_converter,
    'update_clang': generic_shellcommand_converter, #TODO(aneeshm): convert to
    # use the path module?
    'nacl_integration': generic_shellcommand_converter, #TODO(aneeshm): as above
    'nacl_sdk_buildbot_run': nacl_sdk_buildbot_run_converter,
    'nacl_sdk_buildbot_run_win': nacl_sdk_buildbot_run_converter,
    'gclient_clobber': null_converter,
}

def signature_match(step, signature):
  # Simple attributes are those for which an equality comparison suffices to
  # test for equality.
  simple_attributes = {'description',
                       'descriptionDone',
                       'name',
                       'workdir',
                       'mode',
                       'repourl',
                       'branch',
                       'blocksize',
                       'maindest',
                       'subordinatedest',
                       'mainsrc',
                       'subordinatesrc',
                       'strip'}
  subset_dictionary_attributes = {'env'}
  special_attributes = {'command'}
  all_attributes = simple_attributes | special_attributes | \
      subset_dictionary_attributes

  # Specific matching functions for complex attributes
  def list_startswith(base_list, prefix_list):
    if len(prefix_list) > len(base_list):
      return False
    if cmp(base_list[:len(prefix_list)], prefix_list) != 0:
      return False
    return True

  def command_matcher(base_command, command_signature):
    if isinstance(base_command, str):
      return base_command == command_signature
    if isinstance(base_command, list):
      return list_startswith(base_command, command_signature)
    if isinstance(base_command, main.optional_arguments.ListProperties):
      return list_startswith(base_command.items, command_signature)
    if isinstance(base_command, buildbot.process.properties.WithProperties):
      return base_command.fmtstring == command_signature
    return False

  def is_subdictionary(containing_dict, subdict):
    return set(subdict.items()).issubset(set(containing_dict.items()))

  attribute_match = {}
  # For simple attributes, an equality comparison suffices.
  for attribute in simple_attributes:
    attribute_match[attribute] = lambda x, y: x == y
  for attribute in subset_dictionary_attributes:
    attribute_match[attribute] = is_subdictionary
  attribute_match['command'] = command_matcher

  if step[0] != signature[0]:
    return False

  # To let the programmer (aneeshm) know which attributes need to be covered.
  for attribute in step[1]:
    if attribute not in all_attributes:
      # TODO: Should this be an error?
      sys.stderr.write("Attribute '%s' unknown to signature_match" % attribute)

  # If the step is missing an attribute from the signature, it cannot match the
  # signature.
  for attribute in signature[1]:
    if attribute not in step[1]:
      return False

  # For all attributes in the signature, match against the corresponding
  # attribute in the step.
  for attribute in signature[1]:
    if not attribute_match[attribute](step[1][attribute],
                                   signature[1][attribute]):
      return False

  # No attribute checks failed; by definition, this means that the step matched
  # the signature.
  return True


def step_matches(step):
  matches = set()
  for signature in _step_signatures:
    if signature_match(step, _step_signatures[signature]):
      matches.add(signature)
  return matches


def steplist_match_stats(steplist):
  uniquely_matched = 0
  unmatched = 0
  multiply_matched = 0
  for step in steplist:
    matches = step_matches(step)
    if len(matches) == 0:
      unmatched += 1
    elif len(matches) == 1:
      uniquely_matched += 1
    elif len(matches) > 1:
      multiply_matched += 1
    else:
      assert False, "This is impossible"
  return (uniquely_matched, unmatched, multiply_matched)


def steplist_steps_stats(steplist):
  steps_stats = collections.defaultdict(lambda: 0)
  for step in steplist:
    matches = step_matches(step)
    for step_type in matches:
      steps_stats[step_type] += 1
  return steps_stats


def extract_builder_steplist(c, builder_name):
  for builder in c['builders']:
    if builder['name'] == builder_name:
      return builder['factory'].steps

  raise KeyError("Builder not found.")


def builder_match_stats(c, builder_name):
  return steplist_match_stats(extract_builder_steplist(c, builder_name))


def builder_steps_stats(c, builder_name):
  return steplist_steps_stats(extract_builder_steplist(c, builder_name))


# Should this be split into something that operates on a list of builders, and
# another that extracts that list of builders from a config? Probably.
# TODO: see if this is needed later.
def builderlist_steps_stats(c, builder_name_list):
  builderlist_stats = collections.defaultdict(lambda: 0)
  for builder_name in builder_name_list:
    builder_stats = builder_steps_stats(c, builder_name)
    for step_type in builder_stats:
      builderlist_stats[step_type] += builder_stats[step_type]
  return builderlist_stats


def config_steps_stats(c):
  pass


def repr_report(report, baseindent='', indent='  ', base=True):
  if isinstance(report, str):
    return baseindent + report
  elif isinstance(report, list):
    ret = cStringIO.StringIO()
    for subreport in report[:-1]:
      print >> ret, repr_report(subreport, baseindent+('' if base else indent),
                                indent, False)
    ret.write(repr_report(report[-1], baseindent + ('' if base else indent),
                          indent, False))
    retstr = ret.getvalue()
    ret.close()
    return retstr

def report_step(step):
  matchset = step_matches(step)
  if len(matchset) == 0:
    return "Unmatched step: %s" % step[0].__name__
    # Dump step body here in debug mode.
  elif len(matchset) == 1:
    return matchset.pop()
    # Dump step body here in debug mode.
  elif len(matchset) > 1:
    return "Multiply matched step: %s: %s" % (step[0].__name__, repr(matchset))
    # Dump step body here in debug mode.
  else:
    assert False, "This is impossible"


def report_steplist(steplist):
  return map(report_step, steplist)


def report_builder(c, builder_name):
  report = ['Builder: %s' % builder_name]
  report.append(report_steplist(extract_builder_steplist(c, builder_name)))
  return repr_report(report)


def name_this_function(c, ActiveMain, filename=None):
  if ActiveMain.project_name not in _main_builder_map:
    pass # TODO
  with open(filename, 'w') if filename else sys.stdout as f:
    for builder in _main_builder_map[ActiveMain.project_name]:
      f.write(report_builder(c, builder))
      print >> f, 'Match statistics: %s' % repr(builder_match_stats(c, builder))
      print >> f, 'Step statistics: %s' % repr(builder_steps_stats(c, builder))
      print >> f, '\n'



class recipe_skeleton(object):
  def __init__(self, main_name):
    self.main_name = main_name
    self.deps = set()
    # Required to key by buildername.
    self.deps.add('recipe_engine/properties')
    # Required for api.step.StepFailure
    self.deps.add('recipe_engine/step')
    self.builder_names_to_steps = {}
    self.tests = set()

  def generate(self, c, builder_name_list):
    for builder_name in builder_name_list:
      # build_properties is a variable that lives throughout the life of a
      # given builder's function. It is presumed to exist by bot_update, and
      # made use of wherever build properties are needed, such as to annotated
      # scripts which take or require a '--build_properties={...}' argument.
      rc = recipe_chunk()
      rc.deps.add('recipe_engine/properties')
      rc.steps.append('build_properties = api.properties.legacy()')
      builder_rc = rc + builder_to_recipe_chunk(c, builder_name)
      self.deps = self.deps | builder_rc.deps
      self.tests = self.tests | builder_rc.tests
      self.builder_names_to_steps[builder_name] = builder_rc.steps

  def report_recipe(self):
    def sanitize_builder_name(builder_name):
      return builder_name.replace(' ', '_').replace('(', '_').replace(')', '_')\
                         .replace('.', '_').replace('-', '_')
    sbn = sanitize_builder_name

    report = [
      '# Copyright %d The Chromium Authors.' % datetime.datetime.now().year +\
          ' All rights reserved.',
      '# Use of this source code is governed by a BSD-style license that can' +\
          ' be',
      '# found in the LICENSE file.',
      ''
      ]

    report.append('DEPS = [')
    report.append(map(lambda x: '\'' + x + '\',', sorted(self.deps)))
    report.append(']\n')

    # Per-builder functions.
    for builder_name in self.builder_names_to_steps:
      report.append('def %s_steps(api):' % sbn(builder_name))
      report.append(self.builder_names_to_steps[builder_name])
      report.append('\n')

    # Dispatch directory.
    report.append('dispatch_directory = {')
    dispatch_directory = []
    for builder_name in self.builder_names_to_steps:
      dispatch_directory.append("'%s': %s_steps," %(builder_name,
                                                    sbn(builder_name)))
    report.append(dispatch_directory)
    report.append('}')
    report.append('\n')

    # Builder dispatch.
    report.append('def RunSteps(api):')
    steps = ['if api.properties["buildername"] not in dispatch_directory:',
              ['raise api.step.StepFailure("Builder unsupported by recipe.")'],
              'else:',
              ['dispatch_directory[api.properties["buildername"]](api)'],
            ]
    report.append(steps)
    report.append('')

    # Generate tests.
    report.append('def GenTests(api):')
    for builder_name in self.builder_names_to_steps:
      test_properties = ["api.properties(mainname='%s') +" % self.main_name,
                         "api.properties(buildername='%s') +" % builder_name,
                         "api.properties(revision='123456789abcdef') +",
                         "api.properties(got_revision='123456789abcdef') +",
                         "api.properties(buildnumber='42') +",
                         "api.properties(subordinatename='%s')" % "TestSubordinate",]
      test = ["yield (api.test('%s') +" % sbn(builder_name)] +\
             [test_properties] +\
             ['      )']
      report.append(test)
    test = [
        "yield (api.test('builder_not_in_dispatch_directory') +",
        [
         "api.properties(mainname='%s') +" % self.main_name,
         "api.properties(buildername='nonexistent_builder') +",
         "api.properties(subordinatename='TestSubordinate')"
        ],
        "      )",
        ]
    report.append(test)

    return repr_report(report)

def builder_to_recipe_chunk(c, builder_name):
  return steplist_to_recipe_chunk(extract_builder_steplist(c, builder_name))


def steplist_to_recipe_chunk(steplist):
  return sum(map(step_to_recipe_chunk, steplist), recipe_chunk())


# Fails if a step cannot be converted. Perhaps add graceful degradation later,
# iff required. Pass for now, while testing.
def step_to_recipe_chunk(step):
  logging.debug("step_to_recipe_chunk called")
  logging.debug("Raw step")
  logging.debug(pprint.pformat(step))
  matches = step_matches(step)
  logging.debug("Matches:")
  logging.debug(pprint.pformat(matches))
  if len(matches) != 1:
    logging.debug("Unconvertible step; calling dump_converter")
    ret = dump_converter(step, 'step matched %d times' % len(matches))
    logging.debug("dump_converted step:")
    logging.debug(ret)
    return ret
  step_type = matches.pop()
  if step_type not in _step_converters_map:
    return dump_converter(step,
        'step recognised as "%s", no converter found' % step_type)
  return _step_converters_map[step_type](step)

def write_recipe(c, ActiveMain, filename=None):
  global _GLOBAL_BUILDMASTER_CONFIG
  _GLOBAL_BUILDMASTER_CONFIG = c
  if ActiveMain.project_name not in _main_builder_map:
    pass # TODO
  rs = recipe_skeleton(_main_name_map[ActiveMain.project_name])
  rs.generate(c, _main_builder_map[ActiveMain.project_name])
  filename = filename or _main_name_map[ActiveMain.project_name] +\
      '.recipe_autogen.py'
  with open(filename, 'w') as f:
    f.write(rs.report_recipe())

def write_builderlist_converted(c, buildername, filename):
  builder_steplist = extract_builder_steplist(c, buildername)
  with open(filename, 'w') as f:
    print >> f, "%d" % len(builder_steplist)
    i = 0
    for step in builder_steplist:
      print >> f, ">>> Step %d raw:" % i
      print >> f, pprint.pformat(step, indent=2)
      print >> f, ">>> Step %d converted:" % i
      print >> f, step_to_recipe_chunk(step)
      i = i + 1

def write_step(c, buildername, stepnumber, filename):
  step = extract_builder_steplist(c, buildername)[stepnumber]
  with open(filename, 'w') as f:
    print >> f, ">>> Raw"
    print >> f, pprint.pformat(step)
    print >> f, ">>> Converted"
    print >> f, step_to_recipe_chunk(step)

def write_numsteps_builder(c, buildername, filename):
  with open(filename, 'w') as f:
    f.write(str(len(extract_builder_steplist(c, buildername))))

def write_builder_steplist(c, builder_name, filename):
  with open(filename, 'w') as f:
    f.write(pprint.pformat(extract_builder_steplist(c, builder_name), indent=2))
