# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from slave import recipe_api

import common

SIMPLE_TESTS_TO_RUN = [
  'content_gl_tests',
  'gl_tests',
  'angle_unittests'
]

SIMPLE_NON_OPEN_SOURCE_TESTS_TO_RUN = [
  'gles2_conform_test',
]

D3D9_TEST_NAME_MAPPING = {
  'gles2_conform_test': 'gles2_conform_d3d9_test',
  'webgl_conformance': 'webgl_conformance_d3d9'
}

class GpuApi(recipe_api.RecipeApi):
  def setup(self):
    """Call this once before any of the other APIs in this module."""

    # These values may be replaced by external configuration later
    self._dashboard_upload_url = 'https://chromeperf.appspot.com'
    self._gs_bucket_name = 'chromium-gpu-archive'

    # The infrastructure team has recommended not to use git yet on the
    # bots, but it's useful -- even necessary -- when testing locally.
    # To use, pass "use_git=True" as an argument to run_recipe.py.
    self._use_git = self.m.properties.get('use_git', False)

    self._configuration = 'chromium'
    if self.m.gclient.is_blink_mode:
      self._configuration = 'blink'

    self.m.chromium.set_config(self._configuration, GIT_MODE=self._use_git)
    # This is needed to make GOMA work properly on Mac.
    if self.m.platform.is_mac:
      self.m.chromium.set_config(self._configuration + '_clang',
                                 GIT_MODE=self._use_git)
    self.m.gclient.apply_config('chrome_internal')

    # To catch errors earlier on Release bots, in particular the try
    # servers which are Release mode only, force dcheck and blink
    # asserts on.
    self.m.chromium.apply_config('dcheck')

    # To more easily diagnose failures from logs, enable logging in
    # Blink Release builds.
    self.m.chromium.apply_config('blink_logging_on')

    # Use the default Ash and Aura settings on all bots (specifically Blink
    # bots).
    self.m.chromium.c.gyp_env.GYP_DEFINES.pop('use_ash', None)
    self.m.chromium.c.gyp_env.GYP_DEFINES.pop('use_aura', None)

    # Enable archiving the GPU tests' isolates in chrome_tests.gypi.
    # The non-GPU trybots build the "all" target, and these tests
    # shouldn't be built or run on those bots.
    self.m.chromium.c.gyp_env.GYP_DEFINES['archive_gpu_tests'] = 1

    # TODO(kbr): remove the workaround for http://crbug.com/328249 .
    # See crbug.com/335827 for background on the conditional.
    if not self.m.platform.is_win:
      self.m.chromium.c.gyp_env.GYP_DEFINES['disable_glibcxx_debug'] = 1

    # Don't skip the frame_rate data, as it's needed for the frame rate tests.
    # Per iannucci@, it can be relied upon that solutions[1] is src-internal.
    # Consider managing this in a 'gpu' config.
    del self.m.gclient.c.solutions[1].custom_deps[
        'src/chrome/test/data/perf/frame_rate/private']

    self.m.chromium.c.gyp_env.GYP_DEFINES['internal_gles2_conform_tests'] = 1

    # This recipe requires the use of isolates for running tests.
    self.m.isolate.set_isolate_environment(self.m.chromium.c)

    # The FYI waterfall is being used to test top-of-tree ANGLE with
    # Chromium on all platforms.
    if self.is_fyi_waterfall:
      self.m.gclient.c.solutions[0].custom_vars['angle_revision'] = (
          'refs/remotes/origin/master')

    self.m.step.auto_resolve_conflicts = True

  # TODO(martinis) change this to a property that grabs the revision
  # the first time its run, and then caches the value.
  def get_build_revision(self):
    """Returns the revision of the current build. The pixel and maps
    tests use this value when uploading error images to cloud storage,
    only for naming purposes. This could be changed to use a different
    identifier (for example, the build number on the slave), but using
    this value is convenient for easily identifying results."""
    # On the Blink bots, the 'revision' property alternates between a
    # Chromium and a Blink revision, so is not a good value to use.
    #
    # In all cases on the waterfall, the tester is triggered from a
    # builder which sends down parent_got_revision. The only situation
    # where this doesn't happen is when running the build_and_test
    # recipe locally for testing purposes.
    rev = self.m.properties.get('parent_got_revision')
    if rev:
      return rev
    # Fall back to querying the workspace as a last resort. This should
    # only be necessary on combined builder/testers, which isn't a
    # configuration which actually exists on any waterfall any more. If the
    # build_and_test recipe is being run locally and the checkout is being
    # skipped, then the 'parent_got_revision' property can be specified on
    # the command line as a workaround.
    return self._bot_update.presentation.properties['got_revision']

  def get_webkit_revision(self):
    """Returns the webkit revision of the current build."""
    # In all cases on the waterfall, the tester is triggered from a
    # builder which sends down parent_got_webkit_revision. The only
    # situation where this doesn't happen is when running the
    # build_and_test recipe locally for testing purposes.
    wk_rev = self.m.properties.get('parent_got_webkit_revision')
    if wk_rev:
      return wk_rev
    # Fall back to querying the workspace as a last resort. This should
    # only be necessary on combined builder/testers, which isn't a
    # configuration which actually exists on any waterfall any more. If the
    # build_and_test recipe is being run locally and the checkout is being
    # skipped, then the 'parent_got_webkit_revision' property can be
    # specified on the command line as a workaround.
    return self._bot_update.presentation.properties['got_webkit_revision']

  @property
  def _master_class_name_for_testing(self):
    """Allows the class name of the build master to be mocked for
    local testing by setting the build property
    "master_class_name_for_testing" on the command line. The bots do
    not need to, and should not, set this property. Class names follow
    the naming convention like "ChromiumWebkit" and "ChromiumGPU".
    This value is used by the flakiness dashboard when uploading
    results. See the documentation of the --master-class-name argument
    to runtest.py for full documentation."""
    return self.m.properties.get('master_class_name_for_testing')

  @property
  def is_fyi_waterfall(self):
    """Indicates whether the recipe is running on the GPU FYI waterfall."""
    return self.m.properties['mastername'] == 'chromium.gpu.fyi'

  def checkout_steps(self):
    self._bot_update = self.m.bot_update.ensure_checkout(force=True)

  def compile_steps(self):
    # We only need to runhooks if we're going to compile locally.
    self.m.chromium.runhooks()
    # Since performance tests aren't run on the debug builders, it isn't
    # necessary to build all of the targets there.
    build_tag = '' if self.m.chromium.is_release_build else 'debug_'
    # It's harmless to process the isolate-related targets even if they
    # aren't supported on the current configuration (because the component
    # build is used).
    is_tryserver = self.m.tryserver.is_tryserver
    targets = ['%s_run' % test for test in common.GPU_ISOLATES]
    self.m.isolate.clean_isolated_files(
        self.m.chromium.c.build_dir.join(self.m.chromium.c.build_config_fs))
    if is_tryserver:
      try:
        self.m.chromium.compile(targets, name='compile (with patch)')
      except self.m.step.StepFailure:
        if self.m.platform.is_win:
          self.m.chromium.taskkill()
        bot_update_json = self._bot_update.json.output
        self.m.gclient.c.revisions['src'] = str(
            bot_update_json['properties']['got_revision'])
        self.m.bot_update.ensure_checkout(force=True,
                                          patch=False,
                                          update_presentation=False)
        try:
          self.m.chromium.runhooks()
          self.m.chromium.compile(targets, name='compile (without patch)')

          # TODO(phajdan.jr): Set failed tryjob result after recognizing infra
          # compile failures. We've seen cases of compile with patch failing
          # with build steps getting killed, compile without patch succeeding,
          # and compile with patch succeeding on another attempt with same
          # patch.
        except self.m.step.StepFailure:
          self.m.tryserver.set_transient_failure_tryjob_result()
          raise
        raise
    else:
      self.m.chromium.compile(targets=targets, name='compile')
    self.m.isolate.find_isolated_tests(
        self.m.chromium.c.build_dir.join(self.m.chromium.c.build_config_fs),
        common.GPU_ISOLATES)

  def test_steps(self):
    # TODO(kbr): currently some properties are passed to runtest.py via
    # factory_properties in the master.cfg: generate_gtest_json,
    # show_perf_results, test_results_server, and perf_id. runtest.py
    # should be modified to take these arguments on the command line,
    # and the setting of these properties should happen in this recipe
    # instead.

    # Note: we do not run the crash_service on Windows any more now
    # that these bots do not auto-reboot. There's no script which
    # tears it down, and the fact that it's live prevents new builds
    # from being unpacked correctly.

    # Until this is more fully tested, leave this cleanup step local
    # to the GPU recipe.
    if self.m.platform.is_linux:
      try:
        result = self.m.step('killall gnome-keyring-daemon',
                        ['killall', '-9', 'gnome-keyring-daemon'])
      except self.m.step.StepFailure as f:
        result = f.result
      result.presentation.status = self.m.step.SUCCESS

    # Accumulate a list of all the failed test names.
    failures = []
    #TODO(martiniss) change how this processes everything
    def capture(failure):
      if failure:
        failures.append(failure)

    # Note: --no-xvfb is the default.
    # Copy the test list to avoid mutating it.
    basic_tests = list(SIMPLE_TESTS_TO_RUN)
    # Only run tests on the tree closers and on the CQ which are
    # available in the open-source repository.
    if self.is_fyi_waterfall:
      basic_tests += SIMPLE_NON_OPEN_SOURCE_TESTS_TO_RUN

    #TODO(martiniss) convert loop
    for test in basic_tests:
      capture(self._run_isolate(test, args=['--use-gpu-in-tests']))

    # Run closed source tests with ANGLE-D3D9
    if self.is_fyi_waterfall and self.m.platform.is_win:
      for test in SIMPLE_NON_OPEN_SOURCE_TESTS_TO_RUN:
        capture(self._run_isolate(D3D9_TEST_NAME_MAPPING[test],
          args=[
            '--use-gpu-in-tests',
            '--disable-d3d11'
          ],
          isolate_name=test,
          name=D3D9_TEST_NAME_MAPPING[test]))

    # Google Maps Pixel tests.
    capture(self._run_isolated_telemetry_gpu_test(
      'maps', name='maps_pixel_test',
      args=[
        '--build-revision',
        str(self.get_build_revision()),
        '--test-machine-name',
        self.m.properties['buildername']
      ]))

    # Pixel tests.
    # Try servers pull their results from cloud storage; the other
    # tester bots send their results to cloud storage.
    #
    # NOTE that ALL of the bots need to share a bucket. They can't be split
    # by mastername/waterfall, because the try servers are on a different
    # waterfall (tryserver.chromium.*) than the other test bots (chromium.gpu
    # and chromium.webkit, as of this writing). This means there will be
    # races between bots with identical OS/GPU combinations, on different
    # waterfalls, attempting to upload results for new versions of each
    # pixel test. If this is a significant problem in practice then we will
    # have to rethink the cloud storage code in the pixel tests.
    ref_img_arg = '--upload-refimg-to-cloud-storage'
    if self.m.tryserver.is_tryserver:
      ref_img_arg = '--download-refimg-from-cloud-storage'
    cloud_storage_bucket = 'chromium-gpu-archive/reference-images'
    capture(self._run_isolated_telemetry_gpu_test('pixel',
        args=[
            '--build-revision',
            str(self.get_build_revision()),
            ref_img_arg,
            '--refimg-cloud-storage-bucket',
            cloud_storage_bucket,
            '--os-type',
            self.m.chromium.c.TARGET_PLATFORM,
            '--test-machine-name',
            self.m.properties['buildername']
        ],
        name='pixel_test'))

    # WebGL conformance tests.
    capture(self._run_isolated_telemetry_gpu_test('webgl_conformance',
        extra_browser_args=[
          # For diagnosing crbug.com/393331, crbug.com/407976,
          # and crbug.com/408358
          '--blink-platform-log-channels=Timers,Media,'
              'ScriptedAnimationController',
          '--vmodule=thread_proxy=2,render_widget_compositor=2'
        ]))

    # Run extra D3D9 conformance in Windows FYI GPU bots
    # This ensures the ANGLE/D3D9 gets some testing
    if self.is_fyi_waterfall and self.m.platform.is_win:
      capture(self._run_isolated_telemetry_gpu_test('webgl_conformance',
        extra_browser_args=[
          '--disable-d3d11'
        ],
        name=D3D9_TEST_NAME_MAPPING['webgl_conformance']))

    # Context lost tests.
    capture(self._run_isolated_telemetry_gpu_test('context_lost'))

    # Memory tests.
    capture(self._run_isolated_telemetry_gpu_test('memory_test'))

    # Screenshot synchronization tests.
    capture(self._run_isolated_telemetry_gpu_test('screenshot_sync'))

    # Hardware acceleration tests.
    capture(self._run_isolated_telemetry_gpu_test(
      'hardware_accelerated_feature'))

    # GPU process launch tests.
    capture(self._run_isolated_telemetry_gpu_test('gpu_process',
                                                  name='gpu_process_launch'))

    # Smoke test for gpu rasterization of web content.
    capture(self._run_isolated_telemetry_gpu_test(
      'gpu_rasterization',
      args=[
        '--build-revision', str(self.get_build_revision()),
        '--test-machine-name', self.m.properties['buildername']
      ]))

    # Tab capture end-to-end (correctness) tests.
    # This test is unfortunately disabled in Debug builds and the lack
    # of logs is causing alerts. Skip it on Debug bots. crbug.com/403012
    if self.m.chromium.is_release_build:
      capture(self._run_isolate(
          'tab_capture_end2end_tests',
          name='tab_capture_end2end_tests',
          spawn_dbus=True))

    # GPU unit tests.
    capture(self._run_isolate('gpu_unittests', name='gpu_unittests'))

    # Run the content unit tests on all bots except Mac 10.8.
    # TODO(jmadill): Run on all bots once http://crbug.com/421067 is fixed.
    if not "Mac 10.8" in self.m.properties['buildername']:
      capture(self._run_isolate('content_unittests', name='content_unittests'))

    # Run the media unit tests.
    capture(self._run_isolate('media_unittests', name='media_unittests'))

    if failures:
      raise self.m.step.StepFailure('%d tests failed: %r' % (len(failures), failures))

  def _run_isolate(self, test, isolate_name=None, **kwargs):
    # The test_type must end in 'test' or 'tests' in order for the results to
    # automatically show up on the flakiness dashboard.
    #
    # Currently all tests on the GPU bots follow this rule, so we can't add
    # code like in chromium/api.py, run_telemetry_test.
    assert test.endswith('test') or test.endswith('tests')
    # TODO(kbr): turn this into a temporary path. There were problems
    # with the recipe simulation test in doing so and cleaning it up.
    results_directory = self.m.path['slave_build'].join(
      'gtest-results', test)
    try:
      self.m.isolate.runtest(
        isolate_name or test,
        self.get_build_revision(),
        self.get_webkit_revision(),
        annotate='gtest',
        test_type=test,
        generate_json_file=True,
        results_directory=results_directory,
        master_class_name=self._master_class_name_for_testing,
        **kwargs)
    except self.m.step.StepFailure:
      # Return test name in the event of failure
      return test

  def _run_isolated_telemetry_gpu_test(self, test, args=None, name=None,
                                       extra_browser_args=None, **kwargs):
    test_args = ['-v', '--use-devtools-active-port']
    if args:
      test_args.extend(args)
    extra_browser_args_string = '--extra-browser-args=--enable-logging=stderr'
    if extra_browser_args:
      extra_browser_args_string += ' ' + ' '.join(extra_browser_args)
    test_args.append(extra_browser_args_string)
    try:
      self.m.isolate.run_telemetry_test(
        'telemetry_gpu_test',
        test,
        self.get_build_revision(),
        self.get_webkit_revision(),
        args=test_args,
        name=name,
        master_class_name=self._master_class_name_for_testing,
        spawn_dbus=True,
        **kwargs)
    except self.m.step.StepFailure:
      # Return test name in the event of failure
      return test
