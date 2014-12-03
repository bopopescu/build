# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from slave.recipe_config import BadConf

from RECIPE_MODULES.chromium import CONFIG_CTX
from slave.recipe_config_types import Path


@CONFIG_CTX(includes=['chromium'])
def libyuv(c):
  _libyuv_common(c)

  c.runtests.memory_tests_runner = Path('[CHECKOUT]', 'tools',
                                        'valgrind-libyuv', 'libyuv_tests',
                                        platform_ext={'win': '.bat',
                                                      'mac': '.sh',
                                                      'linux': '.sh'})

@CONFIG_CTX(includes=['chromium_clang'])
def libyuv_clang(c):
  _libyuv_common(c)

@CONFIG_CTX(includes=['chromium_linux_asan'])
def libyuv_asan(c):
  _libyuv_common(c)

@CONFIG_CTX(includes=['android'])
def libyuv_android(c):
  pass

@CONFIG_CTX(includes=['android_clang'])
def libyuv_android_clang(c):
  pass

@CONFIG_CTX(includes=['chromium', 'static_library'])
def libyuv_ios(c):
  if c.HOST_PLATFORM != 'mac':
    raise BadConf('Only "mac" host platform is supported for iOS (got: "%s")' %
                  c.HOST_PLATFORM)
  if c.TARGET_PLATFORM != 'ios':
    raise BadConf('Only "ios" target platform is supported (got: "%s")' %
                  c.TARGET_PLATFORM)
  c.build_config_fs = c.BUILD_CONFIG + '-iphoneos'

  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['OS'] = c.TARGET_PLATFORM
  if c.TARGET_BITS == 64:
    gyp_defs['target_subarch'] = 'arm64'

  _libyuv_common(c)

def _libyuv_common(c):
  c.compile_py.default_targets = ['All']
