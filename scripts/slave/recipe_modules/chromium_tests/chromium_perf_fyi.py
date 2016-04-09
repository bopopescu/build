# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from . import steps


RESULTS_URL = 'https://chromeperf.appspot.com'


def _AddBotSpec(name, platform, parent_builder, perf_id, target_bits):
  SPEC['builders'][name] = {
    'disable_tests': True,
    'bot_type': 'tester',
    'chromium_config_kwargs': {
      'BUILD_CONFIG': 'Release',
      'TARGET_BITS': target_bits,
    },
    'parent_buildername': parent_builder,
    'chromium_config': 'chromium_official',
    'gclient_config': 'perf',
    'testing': {
      'platform': platform,
    },
    'perf-id': perf_id,
    'results-url': RESULTS_URL,
    'tests': [
      steps.DynamicPerfTests(perf_id, platform, target_bits,
                             shard_index=0, num_host_shards=1),
    ],
  }


SPEC = {
  'settings': {
    'build_gs_bucket': 'chrome-perf',
  },
  'builders': {
    'Win x64 FYI Builder': {
      'disable_tests': True,
      'chromium_config': 'chromium_official',
      'gclient_config': 'chromium',
      'gclient_apply_config': ['chrome_internal'],
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 64,
      },
      'bot_type': 'builder',
      'compile_targets': [
        'chromium_builder_perf',
      ],
      'testing': {
        'platform': 'win',
      },
      'chromium_apply_config': ['chromium_perf_fyi']
    },
    'Win Clang Builder': {
      'disable_tests': True,
      'chromium_config': 'chromium_win_clang_official',
      'gclient_config': 'chromium',
      'gclient_apply_config': ['chrome_internal'],
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Release',
        'TARGET_BITS': 32,
      },
      'bot_type': 'builder',
      'compile_targets': [
        'chromium_builder_perf',
      ],
      'testing': {
        'platform': 'win',
      },
      'tests': {
        steps.SizesStep(RESULTS_URL, 'win-clang-builder')
      },
      'chromium_apply_config': ['chromium_perf_fyi'],
    },
  },
}

_AddBotSpec(
    name='Win 7 Intel GPU Perf (Xeon)',
    platform='win',
    parent_builder='Win x64 FYI Builder',
    perf_id='chromium-rel-win7-gpu-intel',
    target_bits=64)

_AddBotSpec(
    name='Win Clang Perf',
    platform='win',
    parent_builder='Win Clang Builder',
    perf_id='chromium-win-clang',
    target_bits=32)
