# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common steps for recipes that sync/build Cronet sources."""

from recipe_engine.types import freeze
from recipe_engine import recipe_api

class CronetApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(CronetApi, self).__init__(**kwargs)
    self._repo_path = None

  INSTRUMENTATION_TESTS = freeze([
    {
      'target': 'cronet_sample_test_apk',
    },
    {
      'target': 'cronet_test_instrumentation_apk',
    },
  ])

  UNIT_TESTS = freeze([
    'cronet_unittests',
    'net_unittests',
  ])

  DASHBOARD_UPLOAD_URL = 'https://chromeperf.appspot.com'

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
    droid.init_and_sync(use_bot_update=True)


  def build(self, use_revision=True):
    self.m.chromium.runhooks()
    if self.m.chromium.c.project_generator.tool == 'mb':
      self.m.chromium.run_mb(
          self.m.properties['mainname'],
          self.m.properties['buildername'])
    self.m.chromium.compile()


  def get_version(self):
    version = self.m.chromium.get_version()
    return "%s.%s.%s.%s" % (version['MAJOR'], version['MINOR'],
                            version['BUILD'], version['PATCH'])


  def upload_package(self, build_config):
    droid = self.m.chromium_android
    cronetdir = self.m.path['checkout'].join('out',
                                             droid.c.BUILD_CONFIG,
                                             'cronet')
    destdir = self.get_version() + '/' + build_config
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


  def sizes(self, perf_id):
    self.m.chromium.sizes(results_url=self.DASHBOARD_UPLOAD_URL,
                          perf_id=perf_id, platform='android-cronet')


  def run_tests(
      self, build_config, unit_tests=UNIT_TESTS,
      instrumentation_tests=INSTRUMENTATION_TESTS):
    droid = self.m.chromium_android
    checkout_path = self.m.path['checkout']
    droid.common_tests_setup_steps()
    with self.m.step.defer_results():
      for suite in unit_tests:
        droid.run_test_suite(suite, shard_timeout=180)
      for suite in instrumentation_tests:
        droid.run_instrumentation_suite(
            name=suite['target'],
            verbose=True,
            wrapper_script_suite_name=suite['target'],
            num_retries=0,
            **suite.get('kwargs', {}))
      droid.common_tests_final_steps()

