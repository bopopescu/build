# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from recipe_engine import recipe_api


class iOSApi(recipe_api.RecipeApi):
  def __init__(self, *args, **kwargs):
    super(iOSApi, self).__init__(*args, **kwargs)
    self.__config = None

  def host_info(self):
    """Emits information about the current host and available tools."""
    step_result = self.m.step('host and tools info', [
      self.package_repo_resource(
        'scripts', 'subordinate', 'ios', 'host_info.py'),
      '--json-file', self.m.json.output(),
    ], infra_step=True, step_test_data=self.test_api.host_info)

    if step_result.json.output:
      step_result.presentation.step_text = '<br />OS X %s, Xcode %s (%s)' % (
        step_result.json.output['Mac OS X Version'],
        step_result.json.output['Xcode Version'],
        step_result.json.output['Xcode Build Version'],
      )
    return step_result

  def checkout(self, **kwargs):
    """Checks out Chromium."""
    kwargs.setdefault('force', True)
    self.m.gclient.set_config('ios')
    update_step = self.m.bot_update.ensure_checkout(**kwargs)
    self.m.path['checkout'] = self.m.path['subordinate_build'].join('src')
    return update_step

  @property
  def compiler(self):
    assert self.__config is not None
    return self.__config['compiler']

  @property
  def configuration(self):
    assert self.__config is not None
    return self.__config['configuration']

  @property
  def using_gyp(self):
    assert self.__config is not None
    return not self.using_mb or self.__config.get('mb_type') == 'gyp'

  @property
  def using_mb(self):
    assert self.__config is not None
    # MB and GN only work if we're doing ninja builds, so we will
    # ignore the mb_type setting if compiler isn't set to ninja.
    return self.__config['mb_type'] is not None and self.compiler == 'ninja'

  @property
  def platform(self):
    assert self.__config is not None
    if self.__config['sdk'].startswith('iphoneos'):
      return 'device'
    elif self.__config['sdk'].startswith('iphonesimulator'):
      return 'simulator'

  def read_build_config(
    self,
    main_name=None,
    build_config_dir=None,
    include_dir=None,
    buildername=None,
  ):
    """Reads the iOS build config for this bot.

    Args:
      main_name: Name of a main to read the build config from, or None
        to read from buildbot properties at run-time.
      build_config_dir: Directory to read the build config from, or None
        to read from the default directory.
      include_dir: Directory to read includes from, or None to read from
        the default directory.
    """
    build_config_dir = build_config_dir or self.m.path['checkout'].join(
      'ios',
      'build',
      'bots',
      main_name or self.m.properties['mainname'],
    )
    include_dir = include_dir or self.m.path['checkout'].join(
      'ios',
      'build',
      'bots',
      'tests',
    )
    buildername = buildername or self.m.properties['buildername']

    self.__config = self.m.json.read(
      'read build config',
      build_config_dir.join('%s.json' % buildername),
      step_test_data=lambda: self.m.json.test_api.output(
        self._test_data['build_config']
      ),
    ).json.output

    # If this bot is triggered by another bot, then the build configuration
    # has to be read from the parent's build config. A triggered bot only
    # specifies the tests.
    parent = str(self.__config.get('triggered by', ''))

    if parent:
      parent_config = self.m.json.read(
        'read parent build config (%s)' % parent,
        build_config_dir.join('%s.json' % parent),
        step_test_data=lambda: self.m.json.test_api.output(
          self._test_data['parent_build_config'],
        ),
      ).json.output

      for key in (
        'xcode version',
        'GYP_DEFINES',
        'compiler',
        'configuration',
        'sdk',
      ):
        self.__config[key] = parent_config[key]

    # In the older dict-based bot configs we didn't set these values
    # since they were the same on every bot. In the newer configs they
    # are set anyway since MB needs them as well.
    if isinstance(self.__config['GYP_DEFINES'], dict):
      self.__config['GYP_DEFINES']['component'] = 'static_library'
      self.__config['GYP_DEFINES']['OS'] = 'ios'

    # TODO(crbug.com/552146): Once 'all' works, the default should be ['all'].
    self.__config.setdefault('additional_compile_targets', ['All'])

    # In order to simplify the code that uses the values of self.__config, here
    # we default to empty values of their respective types, so in other places
    # we can iterate over them without having to check if they are in the dict
    # at all.
    self.__config.setdefault('triggered bots', {})
    self.__config.setdefault('tests', [])
    self.__config.setdefault('env', {})
    self.__config.setdefault('mb_type', None)
    self.__config.setdefault('gn_args', [])
    self.__config.setdefault('use_analyze', True)

    # Elements of the "tests" list are dicts. There are two types of elements,
    # determined by the presence of one of these mutually exclusive keys:
    #   "app": This says to run a particular app.
    #   "include": This says to include a common set of tests from include_dir.
    # So now we go through the "tests" list replacing any "include" keys.
    # The value of an "include" key is the name of a set of tests to include,
    # which can be found as a .json file in include_dir. Read the contents
    # lazily as needed into includes.
    def read_include(includes):
      """Reads the contents of the given include.

      Args:
        include: Name of the include.
      """
      return self.m.json.read(
        'include %s' % include,
        include_dir.join(include),
        step_test_data=lambda: self.m.json.test_api.output({
          'tests': [
            {
              'app': 'fake included test 1',
            },
            {
              'app': 'fake included test 2',
            },
          ],
        }),
      ).json.output

    includes = {}
    expanded_tests_list = []

    # expanded_tests_list will be the list of test dicts, with
    # any "include" replaced with the tests from that include.
    for element in self.__config['tests']:
      if element.get('include'):
        # This is an include dict.
        include = str(element.pop('include'))

        # Lazily read the include if we haven't already.
        if include not in includes:
          includes[include] = read_include(include)

        # Now take each test dict from the include, update it with the
        # extra keys (e.g. device, OS), and append to the list of tests.
        for included_test in includes[include]['tests']:
          expanded_tests_list.append(copy.deepcopy(included_test))
          expanded_tests_list[-1].update(element)
      else:
        # This is a test dict.
        expanded_tests_list.append(element)

    self.__config['tests'] = expanded_tests_list

    self.m.step('finalize build config', [
      'echo',
      '-e',
      self.m.json.dumps(self.__config, indent=2),
    ])

    step_result = self.m.step(
      'find xcode', [
      self.package_repo_resource(
        'scripts', 'subordinate', 'ios', 'find_xcode.py'),
      '--json-file', self.m.json.output(),
      '--version', self.__config['xcode version'],
    ], step_test_data=lambda: self.m.json.test_api.output({}))

    cfg = self.m.chromium.make_config()

    if self.using_gyp:
      cfg.gyp_env.GYP_CROSSCOMPILE = 1
      cfg.gyp_env.GYP_DEFINES = copy.deepcopy(self.__config['GYP_DEFINES'])
    self.m.chromium.c = cfg

  def build(self, mb_config_path=None, suffix=None):
    """Builds from this bot's build config."""
    assert self.__config is not None

    suffix = ' (%s)' % suffix if suffix else ''

    if self.using_mb:
      self.m.chromium.c.project_generator.tool = 'mb'

    # Add the default GYP_DEFINES.
    if isinstance(self.__config['GYP_DEFINES'], dict):
      gyp_defines = [
        '%s=%s' % (k, v) for k, v in self.__config['GYP_DEFINES'].iteritems()
      ]
    else:
      gyp_defines = self.__config['GYP_DEFINES']

    mb_type = self.__config['mb_type']
    gn_args = self.__config['gn_args']

    env = {
      'GYP_DEFINES': ' '.join(gyp_defines),
      'LANDMINES_VERBOSE': '1',
    }

    # Add extra env variables.
    env.update(self.__config['env'])

    build_sub_path = ''

    if self.compiler == 'xcodebuild':
      env['GYP_GENERATORS'] = 'xcode'
      env['GYP_GENERATOR_FLAGS'] = 'xcode_project_version=3.2'
      cwd = self.m.path['checkout'].join('xcodebuild')
      cmd = [
        'xcodebuild',
        '-configuration', self.configuration,
        '-project', self.m.path['checkout'].join(
          'build',
          'all.xcodeproj',
        ),
        '-sdk', self.__config['sdk'],
      ]
    elif self.compiler == 'ninja':
      env['GYP_CROSSCOMPILE'] = '1'
      env['GYP_GENERATORS'] = 'ninja'
      build_sub_path = '%s-%s' % (self.configuration, {
          'simulator': 'iphonesimulator',
          'device': 'iphoneos',
        }[self.platform])

      cwd = self.m.path['checkout'].join('out', build_sub_path)
      compile_targets = self.__config['additional_compile_targets']
      cmd = ['ninja', '-C', cwd]

    if self.using_mb:
      # if we're using MB to generate build files, make sure we don't
      # invoke GYP directly. We still want the GYP_DEFINES set in the
      # environment, though, so that other hooks can key off of them.
      env['GYP_CHROMIUM_NO_ACTION'] = '1'

    step_result = self.m.gclient.runhooks(name='runhooks' + suffix, env=env)
    step_result.presentation.step_text = (
      '<br />GYP_DEFINES:<br />%s' % '<br />'.join(gyp_defines)
    )
    if self.using_mb:
      step_result.presentation.step_text += '<br />GYP_CHROMIUM_NO_ACTION=1'

    if self.using_mb:
      self.m.chromium.run_mb(self.m.properties['mainname'],
                             self.m.properties['buildername'],
                             name='generate_build_files' + suffix,
                             mb_config_path=mb_config_path,
                             build_dir='//out/' + build_sub_path)

    use_analyze = self.__config['use_analyze']
    if (use_analyze and
        self.compiler == 'ninja' and
        self.m.tryserver.is_tryserver and
        'without patch' not in suffix):
      affected_files = self.m.tryserver.get_files_affected_by_patch()
      # The same test may be configured to run on multiple simulators.
      # Only specify each test once for the analyzer.
      tests = list(set(test['app'] for test in self.__config['tests']))

      test_targets, compile_targets = (
        self.m.chromium_tests.analyze(
          affected_files,
          tests,
          self.__config['additional_compile_targets'] + tests,
          'trybot_analyze_config.json',
          additional_names=['chromium', 'ios']
        )
      )

      test_targets = set(test_targets)

      for test in self.__config['tests']:
        if test['app'] not in test_targets:
          test['skip'] = True

      if compile_targets: # pragma: no cover
        cmd.extend(compile_targets)
      else:
        return

    use_goma = (self.compiler == 'ninja' and
                ('use_goma=1' in gyp_defines or 'use_goma=true' in gn_args))
    if use_goma:
      self.m.chromium.apply_config('ninja')
      self.m.chromium.apply_config('default_compiler')
      self.m.chromium.apply_config('goma')
      self.m.chromium.compile(targets=compile_targets,
                              target=build_sub_path,
                              cwd=cwd)
    else:
      self.m.step('compile' + suffix, cmd, cwd=cwd)

  def test(self, *args):
    """Runs tests as instructed by this bot's build config.

    Args:
      *args: Any additional arguments to pass to the test harness.
    """
    assert self.__config is not None
    test_failures = []
    infrastructure_failures = []

    for test in self.__config['tests']:
      cmd = [
        self.package_repo_resource(
          'scripts', 'subordinate', 'ios', 'run.py'),
        '--app', self.m.path['subordinate_build'].join(
          self.most_recent_app_dir,
          '%s.app' % test['app'],
        ),
        '--json_file', self.m.json.output(),
      ]

      step_name = test['app']

      if self.platform == 'simulator':
        cmd.extend([
          '--iossim', self.m.path['subordinate_build'].join(self.most_recent_iossim),
          '--platform', test['device type'],
          '--version', test['os'],
        ])

        # Since we may be running simulator tests on multiple platforms,
        # include the platform and OS in the name of the step.
        step_name = '%s (%s iOS %s)' % (
          test['app'],
          test['device type'],
          test['os'],
        )

      cmd.extend(args)

      if test.get('skip'):
        step_result = self.m.step('[skipped] %s' % str(step_name), [])
        step_result.presentation.step_text = (
          'This test was skipped because it was not affected.'
        )
        continue

      try:
        step_result = self.m.step(
          str(step_name),
          cmd,
          step_test_data=self.test_api.test_results,
        )
      except self.m.step.StepFailure as f:
        step_result = f.result

        # The test scripts use a return code of 2 to indicate
        # an infrastructure failure.
        if step_result.retcode == 2:
          step_result.presentation.status = self.m.step.EXCEPTION
          infrastructure_failures.append(step_name)
        else:
          test_failures.append(step_name)

      if step_result.json.output:
        step_result.presentation.logs.update(
          step_result.json.output.get('logs', {})
        )
        step_result.presentation.links.update(
          step_result.json.output.get('links', {})
        )
        step_result.presentation.step_text = (
          step_result.json.output.get('step_text', '')
        )

    # Here we turn the build red if there were any test failures, or purple if
    # there were any infrastructure failures. If there were both, turn the build
    # red to call sheriff attention to the legitimate failures.
    if test_failures:
      raise self.m.step.StepFailure(
        'Failed %s.' % ', '.join(test_failures + infrastructure_failures)
      )
    elif infrastructure_failures:
      raise self.m.step.InfraFailure(
        'Failed %s.' % ', '.join(infrastructure_failures)
      )

  @property
  def most_recent_app_dir(self):
    """Returns the path to the directory of the most recently compiled apps."""
    build_dir = {
      'xcodebuild': 'xcodebuild',
      'ninja': 'out',
    }[self.compiler]

    platform = {
      'device': 'iphoneos',
      'simulator': 'iphonesimulator',
    }[self.platform]

    return self.m.path.join(
      'src',
      build_dir,
      '%s-%s' % (self.configuration, platform),
    )

  @property
  def most_recent_iossim(self):
    """Returns the path to the most recently compiled iossim."""
    build_dir = {
      'xcodebuild': self.m.path.join('xcodebuild', 'ninja-iossim'),
      'ninja': 'out',
    }[self.compiler]

    # If built with Xcode, the iossim path depends on whether the target is
    # Debug or Release, but doesn't depend on the platform.
    # i.e. iossim is located at one of:
    # xcodebuild/ninja-iossim/Debug/iossim
    # xcodebuild/ninja-iossim/Release/iossim
    # However if built with ninja, the iossim path does depend on the platform
    # as well.
    # i.e. iossim could be located at:
    # out/Debug-iphoneos/iossim
    # out/Debug-iphonesimulator/iossim
    # out/Release-iphoneos/iossim
    # out/Release-iphonesimulator/iossim

    platform = {
      'device': 'iphoneos',
      'simulator': 'iphonesimulator',
    }[self.platform]

    return {
      'xcodebuild': self.m.path.join(
        'src',
        build_dir,
        self.configuration,
        'iossim',
      ),
      'ninja': self.m.path.join(
        'src',
         build_dir,
         '%s-%s' % (self.configuration, platform),
         'iossim',
      ),
    }[self.compiler]
