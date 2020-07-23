# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from recipe_engine import recipe_api
from recipe_engine import util as recipe_util

class TestLauncherFilterFileInputPlaceholder(recipe_util.InputPlaceholder):
  def __init__(self, api, tests):
    self.raw = api.m.raw_io.input('\n'.join(tests))
    super(TestLauncherFilterFileInputPlaceholder, self).__init__()

  def render(self, test):
    result = self.raw.render(test)
    if not test.enabled:  # pragma: no cover
      result[0] = '--test-launcher-filter-file=%s' % result[0]
    return result

  def cleanup(self, test_enabled):
    self.raw.cleanup(test_enabled)


class ChromiumApi(recipe_api.RecipeApi):
  def __init__(self, *args, **kwargs):
    super(ChromiumApi, self).__init__(*args, **kwargs)
    self._build_properties = None

  def get_config_defaults(self):
    return {
      'HOST_PLATFORM': self.m.platform.name,
      'HOST_ARCH': self.m.platform.arch,
      'HOST_BITS': self.m.platform.bits,

      'TARGET_PLATFORM': self.m.platform.name,
      'TARGET_ARCH': self.m.platform.arch,
      'TARGET_CROS_BOARD': None,

      # NOTE: This is replicating logic which lives in
      # chrome/trunk/src/build/common.gypi, which is undesirable. The desired
      # end-state is that all the configuration logic lives in one place
      # (in chromium/config.py), and the buildside gypfiles are as dumb as
      # possible. However, since the recipes need to accurately contain
      # {TARGET,HOST}_{BITS,ARCH,PLATFORM}, for use across many tools (of which
      # gyp is one tool), we're taking a small risk and replicating the logic
      # here.
      'TARGET_BITS': (
        32 if self.m.platform.name == 'win'
        else self.m.platform.bits),

      'BUILD_CONFIG': self.m.properties.get('build_config', 'Release'),
    }

  def get_env(self):
    ret = {}
    if self.c.env.PATH:
      ret['PATH'] = self.m.path.pathsep.join(
          map(str, self.c.env.PATH) + ['%(PATH)s'])
    if self.c.env.ADB_VENDOR_KEYS:
      ret['ADB_VENDOR_KEYS'] = self.c.env.ADB_VENDOR_KEYS
    if self.c.env.LLVM_FORCE_HEAD_REVISION:
      ret['LLVM_FORCE_HEAD_REVISION'] = self.c.env.LLVM_FORCE_HEAD_REVISION
    if self.c.env.GOMA_STUBBY_PROXY_IP_ADDRESS:
      ret['GOMA_STUBBY_PROXY_IP_ADDRESS'] = \
        self.c.env.GOMA_STUBBY_PROXY_IP_ADDRESS
    if self.c.env.FORCE_MAC_TOOLCHAIN:
      ret['FORCE_MAC_TOOLCHAIN'] = self.c.env.FORCE_MAC_TOOLCHAIN
    return ret

  @property
  def build_properties(self):
    return self._build_properties

  @property
  def output_dir(self):
    """Return the path to the built executable directory."""
    return self.c.build_dir.join(self.c.build_config_fs)

  @property
  def version(self):
    """Returns a version dictionary (after get_version()), e.g.

    { 'MAJOR'": '37', 'MINOR': '0', 'BUILD': '2021', 'PATCH': '0' }
    """
    text = self._version
    output = {}
    for line in text.splitlines():
      [k,v] = line.split('=', 1)
      output[k] = v
    return output

  def get_version(self):
    self._version = self.m.file.read(
        'get version',
        self.m.path['checkout'].join('chrome', 'VERSION'),
        test_data=("MAJOR=37\nMINOR=0\nBUILD=2021\nPATCH=0\n"))
    return self.version

  def set_build_properties(self, props):
    self._build_properties = props

  def configure_bot(self, builders_dict, additional_configs=None):
    """Sets up the configurations and gclient to be ready for bot update.

    builders_dict is a dict of mainname -> 'builders' -> buildername ->
        bot_config.

    The current mainname and buildername are looked up from the
    build properties; we then apply the configs specified in bot_config
    as appropriate.

    Returns a tuple of (buildername, bot_config) for subsequent use in
       the recipe.
    """
    additional_configs = additional_configs or []

    # TODO: crbug.com/358481 . The build_config should probably be a property
    # passed in from the subordinate config, but that doesn't exist today, so we
    # need a lookup mechanism to map bot name to build_config.
    mainname = self.m.properties.get('mainname')
    buildername = self.m.properties.get('buildername')
    main_dict = builders_dict.get(mainname, {})
    bot_config = main_dict.get('builders', {}).get(buildername)

    self.set_config(bot_config.get('chromium_config', 'chromium'),
                    **bot_config.get('chromium_config_kwargs', {}))

    for c in bot_config.get('chromium_apply_config', []):
      self.apply_config(c)

    for c in additional_configs:
      self.apply_config(c)

    # Note that we have to call gclient.set_config() and apply_config() *after*
    # calling chromium.set_config(), above, because otherwise the chromium
    # call would reset the gclient config to its defaults.
    self.m.gclient.set_config(
        'chromium', PATCH_PROJECT=self.m.properties.get('patch_project'))
    for c in bot_config.get('gclient_apply_config', []):
      self.m.gclient.apply_config(c)

    return (buildername, bot_config)

  def compile(self, targets=None, name=None, force_clobber=False, out_dir=None,
              target=None, **kwargs):
    """Return a compile.py invocation."""
    targets = targets or self.c.compile_py.default_targets.as_jsonish()
    assert isinstance(targets, (list, tuple))

    if self.c.gyp_env.GYP_DEFINES.get('clang', 0) == 1:
      # Get the Clang revision before compiling.
      self._clang_version = self.get_clang_version()

    args = [
      '--show-path',
      'python',
      self.package_repo_resource('scripts', 'subordinate', 'compile.py'),
      '--ninja-path', self.m.depot_tools.ninja_path,
      '--target', target or self.c.build_config_fs,
      '--src-dir', self.m.path['checkout'],
      '--goma-cache-dir', self.m.path['goma_cache'],
    ]
    if self.c.compile_py.build_args:
      args += ['--build-args', self.c.compile_py.build_args]
    if self.c.compile_py.build_tool:
      args += ['--build-tool', self.c.compile_py.build_tool]
    if self.m.properties.get('build_data_dir'):
      args += ['--build-data-dir', self.m.properties.get('build_data_dir')]
    if self.c.compile_py.cross_tool:
      args += ['--crosstool', self.c.compile_py.cross_tool]
    if self.c.compile_py.compiler:
      args += ['--compiler', self.c.compile_py.compiler]
      if 'goma' in self.c.compile_py.compiler:
        args += ['--goma-jsonstatus', self.m.json.output()]
    if out_dir:
      args += ['--out-dir', out_dir]
    if self.c.compile_py.mode:
      args += ['--mode', self.c.compile_py.mode]
    if self.c.compile_py.goma_dir:
      args += ['--goma-dir', self.c.compile_py.goma_dir]
    if self.c.compile_py.goma_hermetic:
      args += ['--goma-hermetic', self.c.compile_py.goma_hermetic]
    if self.c.compile_py.goma_enable_remote_link:
      args += ['--goma-enable-remote-link']
    if self.c.compile_py.goma_store_local_run_output:
      args += ['--goma-store-local-run-output']
    if self.c.compile_py.goma_enable_compiler_info_cache:
      args += ['--goma-enable-compiler-info-cache']
    if self.m.tryserver.is_tryserver:
      # We rely on goma to meet cycle time goals on the tryserver. It's better
      # to fail early.
      args += ['--goma-fail-fast', '--goma-disable-local-fallback']
    if self.c.compile_py.ninja_confirm_noop:
      args.append('--ninja-ensure-up-to-date')
    if (self.m.properties.get('clobber') is not None or
        self.c.compile_py.clobber or
        force_clobber):
      args.append('--clobber')
    if self.c.compile_py.pass_arch_flag:
      args += ['--arch', self.c.gyp_env.GYP_DEFINES['target_arch']]
    if self.c.TARGET_CROS_BOARD:
      args += ['--cros-board', self.c.TARGET_CROS_BOARD]

    assert not self.c.compile_py.solution
    args.append('--')
    if self.c.compile_py.build_tool == 'xcode':
      if self.c.compile_py.xcode_project:  # pragma: no cover
        args.extend(['-project', self.c.compile_py.xcode_project])
    else:
      args.extend(targets)

    if self.c.TARGET_CROS_BOARD:
      # Wrap 'compile' through 'cros chrome-sdk'
      kwargs['wrapper'] = self.get_cros_chrome_sdk_wrapper()

    env = self.get_env()
    env.update(kwargs.pop('env', {}))

    try:
      self.m.python(
          name or 'compile',
          self.package_repo_resource('scripts', 'tools', 'runit.py'),
          args,
          env=env,
          **kwargs)
    except self.m.step.StepFailure as e:
      # Handle failures caused by goma.
      if 'goma' in self.c.compile_py.compiler:
        step_result = self.m.step.active_result
        failure_result_code = ''
        try:
          json_status = step_result.json.output['notice'][0]
          if (not json_status.get('infra_status')):
            failure_result_code = 'GOMA_SETUP_FAILURE'
          elif json_status['infra_status']['ping_status_code'] != 200:
            failure_result_code = 'GOMA_PING_FAILURE'
          elif json_status['infra_status'].get('num_user_error', 0) > 0:
            failure_result_code = 'GOMA_BUILD_ERROR'
        except Exception as ex:
          step_result.presentation.logs['exception'] = ['%r' % ex]
          step_result.presentation.status = self.m.step.WARNING

        if failure_result_code:
          # Mark goma setup failure as exception instead of step failure.
          step_result.presentation.status = self.m.step.EXCEPTION
          assert len(failure_result_code) <= 20
          properties = self.m.step.active_result.presentation.properties
          if not properties.get('extra_result_code'):
            properties['extra_result_code'] = []
          properties['extra_result_code'].append(failure_result_code)
          raise self.m.step.InfraFailure('Infra compile failure: %s' % e)

      raise e

  @recipe_util.returns_placeholder
  def test_launcher_filter(self, tests):
    return TestLauncherFilterFileInputPlaceholder(self, tests)

  def runtest(self, test, args=None, xvfb=False, name=None, annotate=None,
              results_url=None, perf_dashboard_id=None, test_type=None,
              python_mode=False, spawn_dbus=True, parallel=False,
              revision=None, webkit_revision=None,
              test_launcher_summary_output=None, flakiness_dash=None,
              perf_id=None, perf_config=None, chartjson_file=False,
              disable_src_side_runtest_py=False, **kwargs):
    """Return a runtest.py invocation."""
    args = args or []
    assert isinstance(args, list)

    t_name, ext = self.m.path.splitext(self.m.path.basename(test))
    if not python_mode and self.m.platform.is_win and ext == '':
      test += '.exe'

    full_args = ['--target', self.c.build_config_fs]
    if self.c.TARGET_PLATFORM == 'android':
      full_args.extend(['--test-platform', 'android'])
    if self.m.platform.is_linux:
      full_args.append('--xvfb' if xvfb else '--no-xvfb')

    properties_json = self.m.json.dumps(self.m.properties.legacy())
    full_args.extend(['--factory-properties', properties_json,
                      '--build-properties', properties_json])

    if annotate:
      full_args.append('--annotate=%s' % annotate)
      kwargs['allow_subannotations'] = True

    if annotate != 'gtest':
      assert not flakiness_dash

    if results_url:
      full_args.append('--results-url=%s' % results_url)
    if perf_dashboard_id:
      full_args.append('--perf-dashboard-id=%s' % perf_dashboard_id)
    if perf_id:
      full_args.append('--perf-id=%s' % perf_id)
    if perf_config:
      full_args.extend(['--perf-config', perf_config])
    # This replaces the step_name that used to be sent via factory_properties.
    if test_type:
      full_args.append('--test-type=%s' % test_type)
    step_name = name or t_name
    full_args.append('--step-name=%s' % step_name)
    if chartjson_file:
      full_args.append('--chartjson-file')
      full_args.append(self.m.json.output())
      kwargs['step_test_data'] = lambda: self.m.json.test_api.output([])
    if test_launcher_summary_output:
      full_args.extend([
        '--test-launcher-summary-output',
        test_launcher_summary_output
      ])
    if flakiness_dash:
      full_args.extend([
        '--generate-json-file',
        '-o', 'gtest-results/%s' % test,
      ])
      # The flakiness dashboard needs the buildnumber, so we assert it here.
      assert self.m.properties.get('buildnumber') is not None

    # These properties are specified on every bot, so pass them down
    # unconditionally.
    full_args.append('--builder-name=%s' % self.m.properties['buildername'])
    full_args.append('--subordinate-name=%s' % self.m.properties['subordinatename'])
    # A couple of the recipes contain tests which don't specify a buildnumber,
    # so make this optional.
    if self.m.properties.get('buildnumber') is not None:
      full_args.append('--build-number=%s' % self.m.properties['buildnumber'])
    if ext == '.py' or python_mode:
      full_args.append('--run-python-script')
    if not spawn_dbus:
      full_args.append('--no-spawn-dbus')
    if revision:
      full_args.append('--revision=%s' % revision)
    if webkit_revision:
      # TODO(kbr): figure out how to cover this line of code with
      # tests after the removal of the GPU recipe. crbug.com/584469
      full_args.append(
          '--webkit-revision=%s' % webkit_revision)  # pragma: no cover

    if (self.c.gyp_env.GYP_DEFINES.get('asan', 0) == 1 or
        self.c.runtests.run_asan_test):
      full_args.append('--enable-asan')
    if self.c.runtests.enable_lsan:
      full_args.append('--enable-lsan')
    if self.c.gyp_env.GYP_DEFINES.get('msan', 0) == 1:
      full_args.append('--enable-msan')
    if self.c.gyp_env.GYP_DEFINES.get('tsan', 0) == 1:
      full_args.append('--enable-tsan')
    if self.c.runtests.memory_tool:
      full_args.extend([
        '--pass-build-dir',
        '--pass-target',
        '--run-shell-script',
        self.c.runtests.memory_tests_runner,
        '--test', t_name,
        '--tool', self.c.runtests.memory_tool,
      ])
    else:
      full_args.append(test)

    full_args.extend(self.c.runtests.test_args)
    full_args.extend(args)

    runtest_path = self.package_repo_resource('scripts', 'subordinate', 'runtest.py')
    if self.c.runtest_py.src_side and not disable_src_side_runtest_py:
      runtest_path = self.m.path['checkout'].join(
          'infra', 'scripts', 'runtest_wrapper.py')
      # Note that -- is needed since full_args are not indended
      # for wrapper script but for real runtest.py .
      full_args = ['--'] + full_args
    return self.m.python(
      step_name,
      runtest_path,
      full_args,
      **kwargs
    )

  def sizes(self, results_url=None, perf_id=None, platform=None, **kwargs):
    """Return a sizes.py invocation.
    This uses runtests.py to upload the results to the perf dashboard."""
    sizes_script = self.package_repo_resource(
        'scripts', 'subordinate', 'chromium', 'sizes.py')
    sizes_args = ['--target', self.c.build_config_fs]
    if platform:
      sizes_args.extend(['--platform', platform])
    else:
      sizes_args.extend(['--platform', self.c.TARGET_PLATFORM])

    run_tests_args = ['--target', self.c.build_config_fs,
                      '--no-xvfb']
    properties_json = self.m.json.dumps(self.m.properties.legacy())
    run_tests_args.extend(['--factory-properties', properties_json,
                           '--build-properties', properties_json])
    run_tests_args.extend(['--test-type=sizes',
                           '--builder-name=%s' % self.m.properties['buildername'],
                           '--subordinate-name=%s' % self.m.properties['subordinatename'],
                           '--build-number=%s' % self.m.properties['buildnumber'],
                           '--run-python-script'])

    if perf_id:
      assert results_url is not None
      run_tests_args.extend(['--annotate=graphing',
                             '--results-url=%s' % results_url,
                             '--perf-dashboard-id=sizes',
                             '--perf-id=%s' % perf_id])

      # If we have a clang revision, add that to the perf data point.
      # TODO(hans): We want this for all perf data, not just sizes.
      if hasattr(self, '_clang_version'):
        clang_rev = re.match(r'(\d+)(-\d+)?', self._clang_version).group(1)
        run_tests_args.append(
            "--perf-config={'r_clang_rev': '%s'}" % clang_rev)

    full_args = run_tests_args + [sizes_script] + sizes_args

    return self.m.python(
        'sizes', self.package_repo_resource('scripts', 'subordinate', 'runtest.py'),
        full_args, allow_subannotations=True, **kwargs)

  def get_clang_version(self, **kwargs):
    step_result = self.m.python(
        'clang_revision',
        self.package_repo_resource('scripts', 'subordinate', 'clang_revision.py'),
        args=['--src-dir', self.m.path['checkout'],
              '--output-json', self.m.json.output()],
        step_test_data=lambda:
            self.m.json.test_api.output({'clang_revision': '123456-7'}),
        allow_subannotations=True,
        env=self.get_env(),
        **kwargs)
    return step_result.json.output['clang_revision']


  def get_cros_chrome_sdk_wrapper(self, clean=False):
    """Returns: a wrapper command for 'cros chrome-sdk'

    Args:
      external: (bool) If True, force the wrapper to prefer external board
          configurations over internal ones, even if the latter is available.
      clean: (bool) If True, instruct the wrapper to clean any previous
          state data.
    """
    assert self.c.TARGET_CROS_BOARD
    wrapper = [
        'cros', 'chrome-sdk',
        '--board=%s' % (self.c.TARGET_CROS_BOARD,),
        '--nocolor',]
    wrapper += self.c.cros_sdk.args
    if self.c.cros_sdk.external:
      wrapper += ['--use-external-config']
    if clean:
      wrapper += ['--clear-sdk-cache']
    if self.c.compile_py.goma_dir:
      wrapper += ['--gomadir', self.c.compile_py.goma_dir]
    if self.c.gyp_env.GYP_DEFINES.get('fastbuild', 0) == 1:
      wrapper += ['--fastbuild']
    wrapper += ['--']
    return wrapper

  def ensure_goma(self):
    # New code is only enabled on whitelisted platforms for now.
    # Other platforms continue to use DEPS-ed goma.
    if not self.m.platform.is_linux:
      return

    # TODO(phajdan.jr): Move goma out of src checkout.
    goma_dir = self.m.path['checkout'].join('build', 'goma', 'client')

    self.c.gyp_env.GYP_DEFINES['gomadir'] = goma_dir
    self.c.compile_py.goma_dir = goma_dir

    self.m.goma.ensure_goma(goma_dir, canary=self.c.compile_py.goma_canary)

  def runhooks(self, **kwargs):
    """Run the build-configuration hooks for chromium."""
    env = self.get_env()
    env.update(kwargs.get('env', {}))

    # CrOS "chrome_sdk" builds fully override GYP_DEFINES in the wrapper. Zero
    # it to not show confusing information in the build logs.
    if not self.c.TARGET_CROS_BOARD:
      # TODO(sbc): Ideally we would not need gyp_env set during runhooks when
      # we are not running gyp, but there are some hooks (such as sysroot
      # installation that peek at GYP_DEFINES and modify thier behaviour
      # accordingly.
      env.update(self.c.gyp_env.as_jsonish())

    if self.c.project_generator.tool != 'gyp':
      env['GYP_CHROMIUM_NO_ACTION'] = 1
    kwargs['env'] = env
    if self.c.TARGET_CROS_BOARD:
      # Wrap 'runhooks' through 'cros chrome-sdk'
      kwargs['wrapper'] = self.get_cros_chrome_sdk_wrapper(clean=True)
    self.m.gclient.runhooks(**kwargs)

  def run_gn(self, use_goma=False):
    gn_args = list(self.c.gn_args)

    # TODO(dpranke): Figure out if we should use the '_x64' thing to
    # consistent w/ GYP, or drop it to be consistent w/ the other platforms.
    build_dir = '//out/%s' % self.c.build_config_fs

    if self.c.BUILD_CONFIG == 'Debug':
      gn_args.append('is_debug=true')
    if self.c.BUILD_CONFIG == 'Release':
      gn_args.append('is_debug=false')

    if self.c.TARGET_PLATFORM == 'android':
      gn_args.append('target_os="android"')
    elif self.c.TARGET_PLATFORM in ('linux', 'mac', 'win'):
      assert self.c.TARGET_BITS == 64
      gn_args.append('target_cpu="x64"')

    if self.c.TARGET_ARCH == 'arm':
      gn_args.append('target_cpu="arm"')

    # TODO: crbug.com/395784.
    # Consider getting the flags to use via the project_generator config
    # and/or modifying the goma config to modify the gn flags directly,
    # rather than setting the gn_args flags via a parameter passed to
    # run_gn(). We shouldn't have *three* different mechanisms to control
    # what args to use.
    if use_goma:
      gn_args.append('use_goma=true')
      gn_args.append('goma_dir="%s"' % self.c.compile_py.goma_dir)
    gn_args.extend(self.c.project_generator.args)

    self.m.python(
        name='gn',
        script=self.m.path['depot_tools'].join('gn.py'),
        args=[
            '--root=%s' % str(self.m.path['checkout']),
            'gen',
            build_dir,
            '--args=%s' % ' '.join(gn_args),
        ])

  def run_mb(self, mainname, buildername, use_goma=False,
             mb_config_path=None, isolated_targets=None, name=None,
             build_dir=None):
    mb_config_path = (mb_config_path or
                      self.m.path['checkout'].join('tools', 'mb',
                                                   'mb_config.pyl'))
    isolated_targets = isolated_targets or []
    build_dir = build_dir or '//out/%s' % self.c.build_config_fs

    args=[
        'gen',
        '-m', mainname,
        '-b', buildername,
        '--config-file', mb_config_path,
    ]

    if use_goma:
      goma_dir = self.c.compile_py.goma_dir
      if not goma_dir:
        # This method defaults to use_goma=True, which doesn't necessarily
        # match build-side configuration. However, MB is configured
        # src-side, and so it might be actually using goma.
        self.ensure_goma()
        goma_dir = self.c.compile_py.goma_dir
      if not goma_dir:
        # TODO(phajdan.jr): update for swarming, http://crbug.com/585401 .
        goma_dir = self.m.path['build'].join('goma')
      args += ['--goma-dir', goma_dir]

    if isolated_targets:
      sorted_isolated_targets = sorted(set(isolated_targets))
      # TODO(dpranke): Change the MB flag to '--isolate-targets-file', maybe?
      data = '\n'.join(sorted_isolated_targets) + '\n'
      args += ['--swarming-targets-file', self.m.raw_io.input(data)]

    args += [build_dir]

    # This runs with no env being passed along, so we get a clean environment
    # without any GYP_DEFINES being present to cause confusion.
    self.m.python(name=name or 'generate_build_files',
                  script=self.m.path['checkout'].join('tools', 'mb', 'mb.py'),
                  args=args)

    # Comes after self.m.python so the log appears in the correct step result.
    result = self.m.step.active_result
    if isolated_targets and result:
      result.presentation.logs['swarming-targets-file.txt'] = (
          sorted_isolated_targets)


  def update_clang(self):
    # The hooks in DEPS call `update.py --if-needed`, which updates clang by
    # default on Mac and Linux, or if clang=1 is in GYP_DEFINES.  This step
    # is only needed on bots that use clang but where --if-needed doesn't update
    # clang. (In practice, this means on Windows when using gn, not gyp.)
    self.m.python(name='update_clang',
                  script=self.m.path['checkout'].join('tools', 'clang',
                                                      'scripts', 'update.py'))

  def taskkill(self):
    self.m.python(
      'taskkill',
      self.package_repo_resource('scripts', 'subordinate', 'kill_processes.py'))

  def cleanup_temp(self):
    self.m.python(
      'cleanup_temp',
      self.package_repo_resource('scripts', 'tools', 'runit.py'),
      ['--show-path',
       'python',
       self.package_repo_resource('scripts', 'subordinate', 'cleanup_temp.py')],
      infra_step=True)

  def process_dumps(self, **kwargs):
    # Dumps are especially useful when other steps (e.g. tests) are failing.
    try:
      self.m.python(
          'process_dumps',
          self.package_repo_resource('scripts', 'subordinate', 'process_dumps.py'),
          ['--target', self.c.build_config_fs],
          infra_step=True,
          **kwargs)
    except self.m.step.InfraFailure:
      pass

  def apply_syzyasan(self):
    args = ['--target', self.c.BUILD_CONFIG]
    self.m.python(
      'apply_syzyasan',
      self.package_repo_resource(
          'scripts', 'subordinate', 'chromium', 'win_apply_syzyasan.py'),
      args)

  def archive_build(self, step_name, gs_bucket, gs_acl=None, mode=None,
                    **kwargs):
    """Returns a step invoking archive_build.py to archive a Chromium build."""

    # archive_build.py insists on inspecting factory properties. For now just
    # provide these options in the format it expects.
    fake_factory_properties = {
        'gclient_env': self.c.gyp_env.as_jsonish(),
        'gs_bucket': 'gs://%s' % gs_bucket,
    }
    if gs_acl is not None:
      fake_factory_properties['gs_acl'] = gs_acl
    if self.c.TARGET_PLATFORM == 'android':
      fake_factory_properties['target_os'] = 'android'

    args = [
        '--target', self.c.BUILD_CONFIG,
        '--factory-properties', self.m.json.dumps(fake_factory_properties),
    ]
    if self.build_properties:
      args += [
        '--build-properties', self.m.json.dumps(self.build_properties),
      ]
    if mode:
      args.extend(['--mode', mode])
    self.m.python(
      step_name,
      self.package_repo_resource(
          'scripts', 'subordinate', 'chromium', 'archive_build.py'),
      args,
      infra_step=True,
      **kwargs)

  def list_perf_tests(self, browser, num_shards, device=None):
    args = ['list', '--browser', browser, '--json-output',
            self.m.json.output(), '--num-shards', num_shards]
    if device:
      args += ['--device', device]

    return self.m.python(
      'List Perf Tests',
      self.m.path['checkout'].join('tools', 'perf', 'run_benchmark'),
      args,
      step_test_data=lambda: self.m.json.test_api.output({
        "steps": {
          "blink_perf.all.release": {
            "cmd": "/usr/bin/python /path/to/run_benchmark --a=1 -v --b=2",
            "perf_dashboard_id": "blink_perf.all",
            "device_affinity": 0
          },
          "blink_perf.all.exact": {
            "cmd": "/usr/bin/python /path/to/run_benchmark --a=1 -v --b=2",
            "perf_dashboard_id": "blink_perf.all",
            "device_affinity": 1 % num_shards
          },
          "blink_perf.dom": {
            "cmd": "/path/to/run_benchmark -v --upload-results blink_perf.dom",
            "perf_dashboard_id": "blink_perf.dom",
            "device_affinity": 1 % num_shards
          },
          "dromaeo.cssqueryjquery.release": {
            "cmd": "/path/to/run_benchmark",
            "perf_dashboard_id": "dromaeo.cssqueryjquery",
            "device_affinity": 11 % num_shards
          },
          "dromaeo.cssqueryjquery": {
            "cmd": "/path/to/run_benchmark",
            "device_affinity": 13 % num_shards
          },
        },
        "version": 2,
      }))

  def get_annotate_by_test_name(self, test_name):
    return 'graphing'

  def download_lto_plugin(self):
    return self.m.python(
        name='download LTO plugin',
        script=self.m.path['checkout'].join(
            'build', 'download_gold_plugin.py'))
