# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common steps for recipes that sync/build Cronet sources."""

from slave import recipe_api

class CronetApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(CronetApi, self).__init__(**kwargs)
    self._repo_path = None


  def init_and_sync(self, recipe_config, kwargs, gyp_defs):
    default_kwargs = {
      'REPO_URL': 'https://chromium.googlesource.com/chromium/src',
      'INTERNAL': False,
      'REPO_NAME': 'src',
      'BUILD_CONFIG': 'Debug'
    }
    droid = self.m.chromium_android
    droid.configure_from_properties(
        recipe_config,
        **dict(default_kwargs.items() + kwargs.items()))
    self.m.chromium.apply_config('cronet_builder')
    self.m.chromium.c.gyp_env.GYP_DEFINES.update(gyp_defs)
    droid.init_and_sync()


  def build(self, use_revision=True):
    droid = self.m.chromium_android
    droid.runhooks()
    droid.compile()


  def upload_package(self, build_config):
    droid = self.m.chromium_android
    revision = self.m.properties.get('revision')
    cronetdir = self.m.path['checkout'].join('out',
                                             droid.c.BUILD_CONFIG,
                                             'cronet')
    destdir = 'cronet-%s-%s' % (build_config, revision)
    # Upload cronet version first to ensure that destdir is created.
    self.m.gsutil.upload(
        source=cronetdir.join('VERSION'),
        bucket='chromium-cronet/android',
        dest=destdir + '/VERSION',
        name='upload_cronet_version',
        link_name='Cronet version')
    self.m.gsutil.upload(
        source=cronetdir,
        bucket='chromium-cronet/android',
        dest=destdir,
        args=['-R'],
        name='upload_cronet_package',
        link_name='Cronet package')


  def run_tests(self, build_config):
    droid = self.m.chromium_android
    checkout_path = self.m.path['checkout']
    droid.common_tests_setup_steps()
    install_cmd = checkout_path.join('build',
                                     'android',
                                     'adb_install_apk.py')
    test_cmd = checkout_path.join('build',
                                  'android',
                                  'test_runner.py')
    build_arg = []
    if build_config == "Release":
        build_arg = ['--release']
    self.m.python('install CronetSample', install_cmd,
        args = build_arg + ['--apk', 'CronetSample.apk'])
    self.m.python('test CronetSample', test_cmd,
        args = ['instrumentation'] +
               build_arg +
               ['--test-apk', 'CronetSampleTest'])
    self.m.python('install CronetTest', install_cmd,
        args = build_arg + ['--apk', 'CronetTest.apk'])
    self.m.python('test CronetTest', test_cmd,
        args = ['instrumentation'] +
               build_arg +
               ['--test-apk','CronetTestInstrumentation'])
    droid.common_tests_final_steps()

