# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import steps

SPEC = {
  'settings': {
    'build_gs_bucket': 'chromium-linux-archive',
  },
  'builders': {
    'Linux Builder': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 64,
      },
      'bot_type': 'builder',
      'compile_targets': [
        'chromium_swarm_tests',
      ],
      'testing': {
        'platform': 'linux',
      },
      'use_isolate': True,
      'enable_swarming': True,
    },
    'Linux Tests': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 64,
      },
      'bot_type': 'tester',
      'test_generators': [
        steps.generate_gtest,
        steps.generate_script,
      ],
      'parent_buildername': 'Linux Builder',
      'testing': {
        'platform': 'linux',
      },
      'enable_swarming': True,
    },
    'Linux Builder (dbg)(32)': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 32,
      },
      'bot_type': 'builder',
      'compile_targets': [
        'google_apis_unittests',
        'sync_integration_tests',
      ],
      'testing': {
        'platform': 'linux',
      },
      'use_isolate': True,
      'enable_swarming': True,
    },
    'Linux Tests (dbg)(1)(32)': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 32,
      },
      'bot_type': 'tester',
      'test_generators': [
        steps.generate_gtest,
        steps.generate_script,
      ],
      'parent_buildername': 'Linux Builder (dbg)(32)',
      'testing': {
        'platform': 'linux',
      },
      'enable_swarming': True,
    },

    'Linux Builder (dbg)': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 64,
      },
      'bot_type': 'builder',
      'testing': {
        'platform': 'linux',
      },
      'enable_swarming': True,
      'use_isolate': True,
    },
    'Linux Tests (dbg)(1)': {
      'recipe_config': 'chromium',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 64,
      },
      'bot_type': 'tester',
      'test_generators': [
        steps.generate_gtest,
        steps.generate_script,
      ],
      'parent_buildername': 'Linux Builder (dbg)',
      'testing': {
        'platform': 'linux',
      },
      'enable_swarming': True,
    },

    'Linux Clang (dbg)': {
      'recipe_config': 'chromium_clang',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 64,
      },
      'compile_targets': [
        'all',
      ],
      'test_generators': [
        steps.generate_gtest,
        steps.generate_script,
      ],
      'testing': {
        'platform': 'linux',
      },
    },

    'Android Builder (dbg)': {
      'recipe_config': 'chromium_android',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 32,
        'TARGET_PLATFORM': 'android',
      },
      'android_config': 'main_builder',
      'bot_type': 'builder',
      'testing': {
        'platform': 'linux',
      },
    },
    'Android Tests (dbg)': {
      'recipe_config': 'chromium_android',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 32,
        'TARGET_PLATFORM': 'android',
      },
      'bot_type': 'tester',
      'parent_buildername': 'Android Builder (dbg)',
      'android_config': 'tests_base',
      'tests': [
        steps.GTestTest('base_unittests'),
        steps.AndroidInstrumentationTest(
            'AndroidWebViewTest', 'android_webview_test_apk',
            test_data='webview:android_webview/test/data/device_files',
            adb_install_apk=(
                'AndroidWebView.apk', 'org.chromium.android_webview.shell')),
        steps.AndroidInstrumentationTest(
            'ChromeShellTest', 'chrome_shell_test_apk',
            test_data='chrome:chrome/test/data/android/device_files',
            adb_install_apk=(
                'ChromeShell.apk', 'org.chromium.chrome.shell')),
        steps.AndroidInstrumentationTest(
            'ContentShellTest', 'content_shell_test_apk',
            test_data='content:content/test/data/android/device_files',
            adb_install_apk=(
                'ContentShell.apk', 'org.chromium.content_shell_apk')),
      ],
      'testing': {
        'platform': 'linux',
      },
    },

    'Android Builder': {
      'recipe_config': 'chromium_android',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
        'TARGET_PLATFORM': 'android',
      },
      'android_config': 'main_builder',
      'bot_type': 'builder',
      'testing': {
        'platform': 'linux',
      },
    },
    'Android Tests': {
      'recipe_config': 'chromium_android',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
        'TARGET_PLATFORM': 'android',
      },
      'bot_type': 'tester',
      'parent_buildername': 'Android Builder',
      'android_config': 'tests_base',
      'tests': [
        steps.GTestTest('base_unittests'),
        steps.AndroidInstrumentationTest(
            'AndroidWebViewTest', 'android_webview_test_apk',
            test_data='webview:android_webview/test/data/device_files',
            adb_install_apk=(
                'AndroidWebView.apk', 'org.chromium.android_webview.shell')),
        steps.AndroidInstrumentationTest(
            'ChromeShellTest', 'chrome_shell_test_apk',
            test_data='chrome:chrome/test/data/android/device_files',
            adb_install_apk=(
                'ChromeShell.apk', 'org.chromium.chrome.shell')),
        steps.AndroidInstrumentationTest(
            'ContentShellTest', 'content_shell_test_apk',
            test_data='content:content/test/data/android/device_files',
            adb_install_apk=(
                'ContentShell.apk', 'org.chromium.content_shell_apk')),
      ],
      'testing': {
        'platform': 'linux',
      },
    },

    'Android Clang Builder (dbg)': {
      'recipe_config': 'chromium_android_clang',
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_BITS': 32,
        'TARGET_PLATFORM': 'android',
      },
      'android_config': 'clang_builder',
      'bot_type': 'builder_tester',
      'testing': {
        'platform': 'linux',
      },
    },
  },
}
