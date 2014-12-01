# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import urllib

from slave import recipe_api

class AndroidApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(AndroidApi, self).__init__(**kwargs)

  def get_config_defaults(self):
    return {
      'REVISION': self.m.properties.get('revision', '')
    }

  def get_env(self):
    return self.m.chromium.get_env()

  @property
  def out_path(self):
    return self.m.path['checkout'].join('out')

  @property
  def coverage_dir(self):
    return self.out_path.join(self.c.BUILD_CONFIG, 'coverage')

  def configure_from_properties(self, config_name, **kwargs):
    self.set_config(config_name, **kwargs)

  def make_zip_archive(self, step_name, archive_name, files=None,
                       preserve_paths=True, filters=None, **kwargs):
    """Creates and stores the archive file.

    Args:
      step_name: Name of the step.
      archive_name: Name of the archive file.
      files: If specified, only include files here instead of out/<target>.
      filters: List of globs to be included in the archive.
      preserve_paths: If True, files will be stored using the subdolders
        in the archive.
    """
    archive_args = ['--target', self.m.chromium.c.BUILD_CONFIG,
                    '--name', archive_name]

    # TODO(luqui): Clean up when these are covered by the external builders.
    if files:              # pragma: no cover
      archive_args.extend(['--files', ','.join(files)])
    if filters:
      archive_args.extend(['--filters', ','.join(filters)])
    if not preserve_paths: # pragma: no cover
      archive_args.append('--ignore-subfolder-names')

    self.m.python(
      step_name,
      str(self.m.path['build'].join(
          'scripts', 'slave', 'android', 'archive_build.py')),
      archive_args,
      infra_step=True,
      **kwargs
    )

  def init_and_sync(self):
    # TODO(sivachandra): Move the setting of the gclient spec below to an
    # internal config extension when they are supported by the recipe system.
    spec = self.m.gclient.make_config('android_bare')
    spec.target_os = ['android']
    s = spec.solutions[0]
    s.name = self.c.deps_dir
    s.url = self.c.REPO_URL
    s.custom_deps = self.c.gclient_custom_deps or {}
    s.deps_file = self.c.deps_file
    s.custom_vars = self.c.gclient_custom_vars or {}
    s.managed = self.c.managed
    s.revision = self.c.revision
    spec.revisions = self.c.revisions

    self.m.gclient.break_locks()
    refs = self.m.properties.get('event.patchSet.ref')
    if refs:
      refs = [refs]
    result = self.m.bot_update.ensure_checkout(spec, refs=refs)
    if not result.json.output['did_run']:
      result = self.m.gclient.checkout(spec)

    # TODO(sivachandra): Manufacture gclient spec such that it contains "src"
    # solution + repo_name solution. Then checkout will be automatically
    # correctly set by gclient.checkout
    self.m.path['checkout'] = self.m.path['slave_build'].join('src')

    self.clean_local_files()

    return result

  def clean_local_files(self):
    target = self.c.BUILD_CONFIG
    debug_info_dumps = self.m.path['checkout'].join('out',
                                                    target,
                                                    'debug_info_dumps')
    test_logs = self.m.path['checkout'].join('out', target, 'test_logs')
    build_product = self.m.path['checkout'].join('out', 'build_product.zip')
    self.m.python.inline(
        'clean local files',
        """
          import shutil, sys, os
          shutil.rmtree(sys.argv[1], True)
          shutil.rmtree(sys.argv[2], True)
          try:
            os.remove(sys.argv[3])
          except OSError:
            pass
          for base, _dirs, files in os.walk(sys.argv[4]):
            for f in files:
              if f.endswith('.pyc'):
                os.remove(os.path.join(base, f))
        """,
        args=[debug_info_dumps, test_logs, build_product,
              self.m.path['checkout']],
        infra_step=True,
    )

  def run_tree_truth(self):
    # TODO(sivachandra): The downstream ToT builder will require
    # 'Show Revisions' step.
    repos = ['src', 'src-internal']
    if self.c.REPO_NAME not in repos:
      repos.append(self.c.REPO_NAME)
    # TODO(sivachandra): Disable subannottations after cleaning up
    # tree_truth.sh.
    self.m.step('tree truth steps',
                [self.m.path['checkout'].join('build', 'tree_truth.sh'),
                self.m.path['checkout']] + repos,
                allow_subannotations=False)

  def runhooks(self, extra_env={}):
    self.m.chromium.runhooks(env=extra_env)

  def compile(self, **kwargs):
    assert 'env' not in kwargs, (
        "chromium_andoid compile clobbers env in keyword arguments")
    kwargs['env'] = self.m.chromium.get_env()
    self.m.chromium.compile(**kwargs)

  def findbugs(self, suffix='', findbugs_options=[]):
    if suffix:
      suffix = ' ' + suffix
    cmd = [self.m.path['checkout'].join('build', 'android',
                                        'findbugs_diff.py')]
    cmd.extend(findbugs_options)

    if self.m.chromium.c.BUILD_CONFIG == 'Release':
      cmd.append('--release-build')

    self.m.step('findbugs%s' %  suffix,
                cmd, env=self.m.chromium.get_env())

    cmd = [self.m.path['checkout'].join('tools', 'android', 'findbugs_plugin',
               'test', 'run_findbugs_plugin_tests.py')]
    if self.m.chromium.c.BUILD_CONFIG == 'Release':
      cmd.append('--release-build')
    self.m.step('findbugs_tests%s' % suffix,
                cmd, env=self.m.chromium.get_env())

  def git_number(self, **kwargs):
    return self.m.step(
        'git_number',
        [self.m.path['depot_tools'].join('git_number.py')],
        stdout = self.m.raw_io.output(),
        step_test_data=(
          lambda:
            self.m.raw_io.test_api.stream_output('3000\n')
        ),
        cwd=self.m.path['checkout'],
        infra_step=True,
        **kwargs)

  def check_webview_licenses(self, suffix=''):
    if suffix:
      suffix = ' ' + suffix
    self.m.python(
        'check licenses%s' % suffix,
        self.m.path['checkout'].join('android_webview',
                                     'tools',
                                     'webview_licenses.py'),
        args=['scan'],
        cwd=self.m.path['checkout'])

  def upload_build(self, bucket, path):
    archive_name = 'build_product.zip'

    zipfile = self.m.path['checkout'].join('out', archive_name)

    self.make_zip_archive(
      'zip_build_product',
      archive_name,
      preserve_paths=True,
      cwd=self.m.path['checkout']
    )

    self.m.gsutil.upload(
        name='upload_build_product',
        source=zipfile,
        bucket=bucket,
        dest=path)

  def download_build(self, bucket, path, extract_path=None):
    zipfile = self.m.path['checkout'].join('out', 'build_product.zip')
    self.m.gsutil.download(
        name='download_build_product',
        bucket=bucket,
        source=path,
        dest=zipfile
    )
    extract_path = extract_path or self.m.path['checkout']
    self.m.step(
      'unzip_build_product',
      ['unzip', '-o', zipfile],
      cwd=extract_path,
      infra_step=True,
    )

  def zip_and_upload_build(self, bucket, path):
    # TODO(luqui): Unify make_zip_archive and upload_build with this
    # (or at least make the difference clear).
    command_parts = [
        '--src-dir', self.m.path['slave_build'].join('src'),
        '--exclude-files', 'lib.target,gen,android_webview,jingle_unittests',
        '--target', self.m.chromium.c.BUILD_CONFIG]
    if path is not None:
      command_parts += ['--build-url', 'gs://%s/%s' % (bucket, path)]
    self.m.python(
        'zip_build',
        self.m.path['build'].join('scripts', 'slave', 'zip_build.py'),
        command_parts)

  def spawn_logcat_monitor(self):
    self.m.step(
        'spawn_logcat_monitor',
        [self.m.path['build'].join('scripts', 'slave', 'daemonizer.py'),
         '--', self.c.cr_build_android.join('adb_logcat_monitor.py'),
         self.m.chromium.c.build_dir.join('logcat')],
        env=self.m.chromium.get_env(),
        infra_step=True)

  def detect_and_setup_devices(self, restart_usb=False, skip_wipe=False,
                               disable_location=False):
    self.device_status_check(restart_usb=restart_usb)
    self.provision_devices(
      skip_wipe=skip_wipe, disable_location=disable_location)

  def device_status_check(self, restart_usb=False, **kwargs):
    args = []
    if restart_usb:
      args = ['--restart-usb']

    try:
      self.m.step(
          'device_status_check',
          [self.m.path['checkout'].join('build', 'android', 'buildbot',
                                'bb_device_status_check.py')] + args,
          env=self.m.chromium.get_env(),
          infra_step=True,
          **kwargs)
    except self.m.step.InfraFailure as f:
      params = {
        'summary': ('Device Offline on %s %s' %
          (self.m.properties['mastername'], self.m.properties['slavename'])),
        'comment': ('Buildbot: %s\n(Please do not change any labels)' %
          self.m.properties['buildername']),
        'labels': 'Restrict-View-Google,OS-Android,Infra,Infra-Labs',
      }
      link = ('https://code.google.com/p/chromium/issues/entry?%s' %
        urllib.urlencode(params))
      f.result.presentation.links.update({
        'report a bug': link
      })
      raise

  def provision_devices(self, skip_wipe=False, disable_location=False,
                        **kwargs):
    args = ['-t', self.m.chromium.c.BUILD_CONFIG]
    if skip_wipe:
      args.append('--skip-wipe')
    if disable_location:
      args.append('--disable-location')
    self.m.python(
      'provision_devices',
      self.m.path['checkout'].join(
          'build', 'android', 'provision_devices.py'),
      args=args,
      env=self.m.chromium.get_env(),
      infra_step=True,
      **kwargs)

  def adb_install_apk(self, apk, apk_package):
    install_cmd = [
        self.m.path['checkout'].join('build',
                                     'android',
                                     'adb_install_apk.py'),
        '--apk', apk,
        '--apk_package', apk_package
    ]
    if self.m.chromium.c.BUILD_CONFIG == 'Release':
      install_cmd.append('--release')
    return self.m.step('install ' + apk, install_cmd,
                       infra_step=True,
                       env=self.m.chromium.get_env())

  def monkey_test(self, **kwargs):
    args = [
        'monkey',
        '-v',
        '--package=%s' % self.c.channel,
        '--event-count=50000'
    ]
    return self.m.python(
        'Monkey Test',
        str(self.m.path['checkout'].join('build', 'android', 'test_runner.py')),
        args,
        env={'BUILDTYPE': self.c.BUILD_CONFIG},
        **kwargs)


  def _run_sharded_tests(self,
                         config='sharded_perf_tests.json',
                         flaky_config=None,
                         chartjson_output=False,
                         **kwargs):
    args = ['perf', '--release', '--verbose', '--steps', config]
    if flaky_config:
      args.extend(['--flaky-steps', flaky_config])
    args.extend(['--collect-chartjson-data'] if chartjson_output else [])

    self.m.python(
        'Sharded Perf Tests',
        self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
        args,
        cwd=self.m.path['checkout'],
        env=self.m.chromium.get_env(),
        **kwargs)

  def run_sharded_perf_tests(self, config, flaky_config=None, perf_id=None,
                             test_type_transform=lambda x: x,
                             chartjson_file=False, **kwargs):
    """Run the perf tests from the given config file.

    config: the path of the config file containing perf tests.
    flaky_config: optional file of tests to avoid.
    perf_id: the id of the builder running these tests
    test_type_transform: a lambda transforming the test name to the
      test_type to upload to.
    """
    # test_runner.py actually runs the tests and records the results
    self._run_sharded_tests(config=config, flaky_config=flaky_config,
                            chartjson_output=chartjson_file, **kwargs)

    # now obtain the list of tests that were executed.
    result = self.m.step(
        'get perf test list',
        [self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
         'perf', '--steps', config, '--output-json-list', self.m.json.output()],
        step_test_data=lambda: self.m.json.test_api.output([
            'perf_test.foo', 'page_cycler.foo']),
        env=self.m.chromium.get_env()
    )
    perf_tests = result.json.output

    failures = []
    for test_name in perf_tests:
      test_name = str(test_name)  # un-unicode
      test_type = test_type_transform(test_name)
      annotate = self.m.chromium.get_annotate_by_test_name(test_name)

      try:
        self.m.chromium.runtest(
          self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
          ['perf', '--print-step', test_name, '--verbose'],
          name=test_name,
          perf_dashboard_id=test_type,
          test_type=test_type,
          annotate=annotate,
          results_url='https://chromeperf.appspot.com',
          perf_id=perf_id,
          env=self.m.chromium.get_env(),
          chartjson_file=chartjson_file)
      except self.m.step.StepFailure as f:
        failures.append(f)

    if failures:
      raise self.m.step.StepFailure('sharded perf tests failed %s' % failures)

  def run_instrumentation_suite(self, test_apk, test_data=None,
                                flakiness_dashboard=None,
                                annotation=None, except_annotation=None,
                                screenshot=False, verbose=False,
                                apk_package=None, host_driven_root=None,
                                official_build=False, install_apk=None,
                                **kwargs):
    if install_apk:
      self.adb_install_apk(install_apk['apk'], install_apk['package'])

    args = ['--test-apk', test_apk]
    if test_data:
      args.extend(['--test_data', test_data])
    if flakiness_dashboard:
      args.extend(['--flakiness-dashboard-server', flakiness_dashboard])
    if annotation:
      args.extend(['-A', annotation])
    if except_annotation:
      args.extend(['-E', except_annotation])
    if screenshot:
      args.append('--screenshot')
    if verbose:
      args.append('--verbose')
    if self.m.chromium.c.BUILD_CONFIG == 'Release':
      args.append('--release')
    if self.c.coverage:
      args.extend(['--coverage-dir', self.coverage_dir,
                   '--python-only'])
    if host_driven_root:
      args.extend(['--host-driven-root', host_driven_root])
    if official_build:
      args.extend(['--official-build'])

    self.m.python(
        'Instrumentation test %s' % (annotation or test_apk),
        self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
        args=['instrumentation'] + args,
        **kwargs)

  def logcat_dump(self, gs_bucket=None):
    if gs_bucket:
      log_path = self.m.chromium.output_dir.join('full_log')
      self.m.python(
          'logcat_dump',
          self.m.path['checkout'].join('build', 'android',
                                       'adb_logcat_printer.py'),
          [ '--output-path', log_path,
            self.m.path['checkout'].join('out', 'logcat') ],
          infra_step=True)
      self.m.gsutil.upload(
          log_path,
          gs_bucket,
          'logcat_dumps/%s/%s' % (self.m.properties['buildername'],
                                  self.m.properties['buildnumber']),
          link_name='logcat dump')
    else:
      self.m.python(
          'logcat_dump',
          self.m.path['build'].join('scripts', 'slave', 'tee.py'),
          [self.m.chromium.output_dir.join('full_log'),
           '--',
           self.m.path['checkout'].join('build', 'android',
                                        'adb_logcat_printer.py'),
           self.m.path['checkout'].join('out', 'logcat')],
          infra_step=True,
          )

  def stack_tool_steps(self):
    log_file = self.m.path['checkout'].join('out',
                                            self.m.chromium.c.BUILD_CONFIG,
                                            'full_log')
    target_arch = self.m.chromium.c.gyp_env.GYP_DEFINES['target_arch']
    # gyp converts ia32 to x86, bot needs to do the same
    target_arch = {'ia32': 'x86'}.get(target_arch) or target_arch
    self.m.step(
        'stack_tool_with_logcat_dump',
        [self.m.path['checkout'].join('third_party', 'android_platform',
                              'development', 'scripts', 'stack'),
         '--arch', target_arch, '--more-info', log_file],
        env=self.m.chromium.get_env(),
        infra_step=True)
    self.m.step(
        'stack_tool_for_tombstones',
        [self.m.path['checkout'].join('build', 'android', 'tombstones.py'),
         '-a', '-s', '-w'], env=self.get_env(),
        infra_step=True)
    if self.c.asan_symbolize:
      self.m.step(
          'stack_tool_for_asan',
          [self.m.path['checkout'].join('build',
                                        'android',
                                        'asan_symbolize.py'),
           '-l', log_file], env=self.m.chromium.get_env(),
          infra_step=True)

  def test_report(self):
    self.m.python.inline(
        'test_report',
         """
            import glob, os, sys
            for report in glob.glob(sys.argv[1]):
              with open(report, 'r') as f:
                for l in f.readlines():
                  print l
              os.remove(report)
         """,
         args=[self.m.path['checkout'].join('out',
                                            self.m.chromium.c.BUILD_CONFIG,
                                            'test_logs',
                                            '*.log')],
    )

  def common_tests_setup_steps(self):
    self.spawn_logcat_monitor()
    self.device_status_check()
    self.provision_devices()

  def common_tests_final_steps(self):
    self.logcat_dump()
    self.stack_tool_steps()
    self.test_report()

  def run_bisect_script(self, extra_src='', path_to_config=''):
    self.m.step('prepare bisect perf regression',
        [self.m.path['checkout'].join('tools',
                                      'prepare-bisect-perf-regression.py'),
         '-w', self.m.path['slave_build']])

    args = []
    if extra_src:
      args = args + ['--extra_src', extra_src]
    if path_to_config:
      args = args + ['--path_to_config', path_to_config]
    self.m.step('run bisect perf regression',
        [self.m.path['checkout'].join('tools',
                                      'run-bisect-perf-regression.py'),
         '-w', self.m.path['slave_build']] + args)

  def run_test_suite(self, suite, verbose=True, isolate_file_path=None,
                     gtest_filter=None, tool=None, flakiness_dashboard=None,
                     **kwargs):
    args = []
    if verbose:
      args.append('--verbose')
    if self.c.BUILD_CONFIG == 'Release':
      args.append('--release')
    if isolate_file_path:
      args.append('--isolate_file_path=%s' % isolate_file_path)
    if gtest_filter:
      args.append('--gtest_filter=%s' % gtest_filter)
    if tool:
      args.append('--tool=%s' % tool)
    if flakiness_dashboard:
      args.append('--flakiness-dashboard-server=%s' %
          flakiness_dashboard)

    self.m.python(
        str(suite),
        self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
        ['gtest', '-s', suite] + args,
        env=self.m.chromium.get_env(),
        **kwargs)

  def run_java_unit_test_suite(self, suite, verbose=True, **kwargs):
    args = []
    if verbose:
      args.append('--verbose')
    if self.c.BUILD_CONFIG == 'Release':
      args.append('--release')

    self.m.python(
        str(suite),
        self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
        ['junit', '-s', suite] + args,
        env=self.m.chromium.get_env(),
        **kwargs)

  def run_python_unit_test_suite(self, suite, verbose=True, **kwargs):
    args = []
    if verbose:
      args.append('--verbose')

    self.m.python(
        str(suite),
        self.m.path['checkout'].join('build', 'android', 'test_runner.py'),
        ['python', '-s', suite] + args,
        env=self.m.chromium.get_env(),
        **kwargs)

  def coverage_report(self, **kwargs):
    assert self.c.coverage, (
        'Trying to generate coverage report but coverage is not enabled')
    gs_dest = 'java/%s/%s' % (
        self.m.properties['buildername'], self.m.properties['revision'])

    self.m.python(
        'Generate coverage report',
        self.m.path['checkout'].join(
            'build', 'android', 'generate_emma_html.py'),
        args=['--coverage-dir', self.coverage_dir,
              '--metadata-dir', self.out_path.join(self.c.BUILD_CONFIG),
              '--cleanup',
              '--output', self.coverage_dir.join('coverage_html',
                                                 'index.html')],
        infra_step=True,
        **kwargs)

    self.m.gsutil.upload(
        source=self.coverage_dir.join('coverage_html'),
        bucket='chrome-code-coverage',
        dest=gs_dest,
        args=['-R'],
        name='upload coverage report',
        link_name='Coverage report',
        **kwargs)
