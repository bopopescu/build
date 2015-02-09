# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import types

from slave.recipe_config import config_item_context, ConfigGroup
from slave.recipe_config import ConfigList, Dict, List, Single, Static
from slave.recipe_config_types import Path

def BaseConfig(INTERNAL=False, REPO_NAME=None, REPO_URL=None,
               BUILD_CONFIG='Debug', REVISION='', **_kwargs):
  return ConfigGroup(
    INTERNAL = Static(INTERNAL),
    REPO_NAME = Static(REPO_NAME),
    REPO_URL = Static(REPO_URL),
    BUILD_CONFIG = Static(BUILD_CONFIG),
    revision = Single(basestring, empty_val=REVISION),
    revisions = Dict(value_type=(basestring, types.NoneType)),
    asan_symbolize = Single(bool, required=False, empty_val=False),
    get_app_manifest_vars = Single(bool, required=False, empty_val=True),
    run_tree_truth = Single(bool, required=False, empty_val=True),
    deps_file = Single(basestring, required=False, empty_val='.DEPS.git'),
    internal_dir_name = Single(basestring, required=False),
    # deps_dir: where to checkout the gclient deps file
    deps_dir = Single(basestring, required=False, empty_val=REPO_NAME),
    managed = Single(bool, required=False, empty_val=True),
    extra_deploy_opts = List(inner_type=basestring),
    tests = List(inner_type=basestring),
    cr_build_android = Static(Path('[CHECKOUT]', 'build', 'android')),
    test_runner = Single(Path),
    gclient_custom_deps = Dict(value_type=(basestring, types.NoneType)),
    storage_bucket = Single(basestring),
    channel = Single(basestring, empty_val='chrome'),
    upload_dest_prefix = Single(basestring, empty_val=''),
    gclient_custom_vars = Dict(value_type=(basestring, types.NoneType)),
    coverage = Single(bool, required=False, empty_val=False),
  )


VAR_TEST_MAP = {
  'INTERNAL': [True, False],
  'REPO_NAME': ['src/clank'],
  'REPO_URL': ['<hidden>'],  # supplied in build properties
  'BUILD_CONFIG': ['Debug', 'Release'],
}

def TEST_NAME_FORMAT(kwargs):
  name = 'repo-%(REPO_NAME)s-from-url-%(REPO_URL)s' % kwargs
  if kwargs['INTERNAL']:
    return name + '-internal'
  else:
    return name

config_ctx = config_item_context(BaseConfig, VAR_TEST_MAP, TEST_NAME_FORMAT)

@config_ctx(is_root=True)
def base_config(c):
  c.internal_dir_name = 'clank'
  c.test_runner = Path('[CHECKOUT]', 'build', 'android', 'test_runner.py')

@config_ctx()
def main_builder(c):
  pass

@config_ctx()
def trybot_builder(c):
  pass

@config_ctx()
def clang_builder(c):
  pass

@config_ctx(config_vars={'BUILD_CONFIG': 'Release'})
def clang_release_builder(c):
  c.asan_symbolize = True
  c.storage_bucket = 'chrome-test-builds/android'
  c.upload_dest_prefix = 'asan-android-release-'

@config_ctx(config_vars={'BUILD_CONFIG': 'Release'})
def clang_release_builder_l(c):
  c.asan_symbolize = True
  c.storage_bucket = 'chrome-test-builds/android'
  c.upload_dest_prefix = 'asan-android-release-l-'

@config_ctx()
def component_builder(c):
  pass

@config_ctx()
def x86_base(c):
  pass

@config_ctx(includes=['x86_base'])
def x86_builder(c):
  pass

@config_ctx()
def mipsel_base(c):
  pass

@config_ctx(includes=['mipsel_base'])
def mipsel_builder(c):
  pass

@config_ctx(includes=['main_builder'])
def dartium_builder(c):
  c.get_app_manifest_vars = False
  c.run_tree_truth = False
  c.deps_file = 'DEPS'
  c.managed = True

@config_ctx()
def arm_l_builder(c):
  pass

@config_ctx()
def arm_l_builder_lto(c):
  pass

@config_ctx()
def arm_l_builder_rel(c):
  pass

@config_ctx()
def x64_base(c):
  pass

@config_ctx(includes=['x64_base'])
def x64_builder(c):
  pass

@config_ctx()
def arm64_builder(c):
  pass

@config_ctx()
def arm64_builder_rel(c):
  pass

@config_ctx()
def try_base(c):
  pass

@config_ctx(includes=['try_base'])
def try_builder(c):
  pass

@config_ctx(includes=['x86_builder', 'try_builder'])
def x86_try_builder(c):
  pass

@config_ctx()
def tests_base(c):
  pass

@config_ctx(includes=['arm64_builder_rel'])
def tests_arm64(c):
  pass

@config_ctx(includes=['x64_builder'])
def tests_x64(c):
  pass

@config_ctx(includes=['tests_base'])
def instrumentation_tests(c):
  c.tests.append('smoke_instrumentation_tests')
  c.tests.append('small_instrumentation_tests')
  c.tests.append('medium_instrumentation_tests')
  c.tests.append('large_instrumentation_tests')

@config_ctx(includes=['instrumentation_tests'])
def main_tests(c):
  pass

@config_ctx(includes=['tests_base'])
def clang_tests(c):
  c.tests.append('smoke_instrumentation_tests')
  c.asan_symbolize = True

@config_ctx(includes=['tests_base'])
def enormous_tests(c):
  c.extra_deploy_opts = ['--await-internet']
  c.tests.append('enormous_instrumentation_tests')

@config_ctx(includes=['try_base', 'instrumentation_tests'])
def try_instrumentation_tests(c):
  pass

@config_ctx(includes=['x86_base', 'try_base', 'instrumentation_tests'])
def x86_try_instrumentation_tests(c):
  c.extra_deploy_opts.append('--non-rooted')

@config_ctx(includes=['main_builder'])
def coverage_builder_tests(c):
  pass

@config_ctx(includes=['component_builder'])
def oilpan_builder(c):
  pass

@config_ctx()
def perf(c):
  pass

@config_ctx()
def webview_perf(c):
  pass
