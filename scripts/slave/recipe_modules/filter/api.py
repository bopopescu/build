# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from recipe_engine import recipe_api

class FilterApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(FilterApi, self).__init__(**kwargs)
    self._test_targets = []
    self._compile_targets = []
    self._paths = []

  def __is_path_in_exclusion_list(self, path, exclusions):
    """Returns true if |path| matches any of the regular expressions in
    |exclusions|."""
    for regex in exclusions:
      match = regex.match(path)
      if match and match.end() == len(path):
        return regex.pattern
    return False

  @property
  def test_targets(self):
    """Returns the set of targets passed to does_patch_require_compile() that
    are affected by the set of files that have changed."""
    return self._test_targets

  @property
  def compile_targets(self):
    """Returns the set of targets that need to be compiled based on the set of
    files that have changed."""
    return self._compile_targets

  @property
  def paths(self):
    """Returns the paths that have changed in this patch."""
    return self._paths

  def _load_analyze_config(self, file_name):
    config_path = self.m.path.join('testing', 'buildbot', file_name)
    step_result = self.m.json.read(
      'read filter exclusion spec',
      self.m.path['checkout'].join(config_path),
      step_test_data=lambda: self.m.json.test_api.output({
          'base': {
            'exclusions': [],
          },
          'chromium': {
            'exclusions': [],
          },
          'ios': {
            'exclusions': [],
          },
        })
      )
    step_result.presentation.step_text = 'path: %r' % config_path
    return step_result.json.output

  def _load_exclusions(self, names, file_name):
    file_contents = self._load_analyze_config(file_name)
    exclusions = []
    for name in names:
      exclusions.extend(file_contents[name]['exclusions'])
    return exclusions

  def does_patch_require_compile(self,
                                 affected_files,
                                 test_targets=None,
                                 additional_compile_targets=None,
                                 additional_names=None,
                                 config_file_name='trybot_analyze_config.json',
                                 use_mb=False,
                                 mb_mainname=None,
                                 mb_buildername=None,
                                 build_output_dir=None,
                                 cros_board=None,
                                 **kwargs):
    """Check to see if the affected files require a compile or tests.

    Args:
      affected_files: list of files affected by the current patch; paths
                      should only use forward slashes ("/") on all platforms
      test_targets: the possible set of executables that are desired to run.
                    When done, test_targets() returns the subsetset of targets
                    that are affected by the files that have changed.
      additional_compile_targets: any targets to compile in addition to
                                  the test_targets.
      additional_names: additional top level keys to look up exclusions in,
                        see |config_file_name|.
      conconfig_file_name: the config file to look up exclusions in.
      mb_mainname: the mainname to pass over to run MB.
      mb_buildername: the buildername to pass over to run MB.

    Within the file we concatenate "base.exclusions" and
    "|additional_names|.exclusions" (if |additional_names| is not none) to
    get the full list of exclusions.

    The exclusions should be a list of Python regular expressions (as strings).

    If any of the files in the current patch match one of the values in
    we assume everything needs to be compiled and tested.

    If an error occurs, an exception is raised. Otherwise, after the
    call completes the results can be obtained from self.compile_targets()
    and self.test_targets().

    To run MB, we need to use the actual mainname and buildername we're
    running on, and not those of the continuous builder the trybot may be
    configured to match, because a trybot may be configured with different MB
    settings.
    However, recipes used by Findit for culprit finding may override the
    defaults with `mb_mainname` and `mb_buildername` to exactly match a given
    continuous builder.
    """

    names = ['base']
    if additional_names:
      names.extend(additional_names)
    exclusions = self._load_exclusions(names, config_file_name)

    test_targets = test_targets or []
    additional_compile_targets = additional_compile_targets or []
    all_targets = sorted(set(test_targets) | set(additional_compile_targets))
    self._test_targets = []
    self._compile_targets = []
    self._paths = affected_files

    # Check the path of each file against the exclusion list. If found, no need
    # to check dependencies.
    exclusion_regexs = [re.compile(exclusion) for exclusion in exclusions]
    for path in self.paths:
      first_match = self.__is_path_in_exclusion_list(path, exclusion_regexs)
      if first_match:
        step_result = self.m.python.inline(
            'analyze',
            'import sys; sys.exit(0)',
            add_python_log=False)
        step_result.presentation.logs.setdefault('excluded_files', []).append(
            '%s (regex = \'%s\')' % (path, first_match))
        self._compile_targets = sorted(all_targets)
        self._test_targets = sorted(test_targets)
        return

    analyze_input = {
        'files': self.paths,
        'test_targets': test_targets,
        'additional_compile_targets': additional_compile_targets,
    }

    test_output = {
        'status': 'No dependency',
        'compile_targets': [],
        'test_targets': [],
    }

    kwargs.setdefault('env', {})

    # If building for CrOS, execute through the "chrome_sdk" wrapper. This will
    # override GYP environment variables, so we'll refrain from defining them
    # to avoid confusing output.
    if cros_board:
      kwargs['wrapper'] = self.m.chromium.get_cros_chrome_sdk_wrapper()
    else:
      kwargs['env'].update(self.m.chromium.c.gyp_env.as_jsonish())

    if use_mb:
      if 'env' in kwargs:
        # Ensure that mb runs in a clean environment to avoid
        # picking up any GYP_DEFINES accidentally.
        del kwargs['env']
      mb_mainname = mb_mainname or self.m.properties['mainname']
      mb_buildername = mb_buildername or self.m.properties['buildername']
      step_result = self.m.python(
          'analyze',
          self.m.path['checkout'].join('tools', 'mb', 'mb.py'),
          args=['analyze',
                '-m',
                mb_mainname,
                '-b',
                mb_buildername,
                '-v',
                build_output_dir,
                self.m.json.input(analyze_input),
                self.m.json.output()],
          step_test_data=lambda: self.m.json.test_api.output(
            test_output),
          **kwargs)
    else:
      step_result = self.m.python(
          'analyze',
          self.m.path['checkout'].join('build', 'gyp_chromium'),
          args=['--analyzer',
                self.m.json.input(analyze_input),
                self.m.json.output()],
          step_test_data=lambda: self.m.json.test_api.output(
            test_output),
          **kwargs)

    if 'error' in step_result.json.output:
      step_result.presentation.step_text = 'Error: ' + \
          step_result.json.output['error']
      raise self.m.step.StepFailure(
          'Error: ' + step_result.json.output['error'])

    if 'invalid_targets' in step_result.json.output:
      raise self.m.step.StepFailure('Error, following targets were not ' + \
          'found: ' + ', '.join(step_result.json.output['invalid_targets']))

    if (step_result.json.output['status'] == 'Found dependency' or
        step_result.json.output['status'] == 'Found dependency (all)'):
      self._compile_targets = step_result.json.output['compile_targets']
      self._test_targets = step_result.json.output['test_targets']

      # TODO(dpranke) crbug.com/557505 - we need to not prune meta
      # targets that are part of 'test_targets', because otherwise
      # we might not actually build all of the binaries needed for
      # a given test, even if they aren't affected by the patch.
      # Until the GYP code is updated, we will merge the returned
      # test_targets into compile_targets to be safe.
      self._compile_targets = sorted(set(self._compile_targets +
                                         self._test_targets))
    else:
      step_result.presentation.step_text = 'No compile necessary'
