# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import random
import re
import urllib

from builders import iter_builders
from recipe_engine.types import freeze
from recipe_engine import recipe_api
from . import bisection
from . import builders
from . import testing


V8_URL = 'https://chromium.googlesource.com/v8/v8'

COMMIT_TEMPLATE = '%s/+/%%s' % V8_URL

# Regular expressions for v8 branch names.
RELEASE_BRANCH_RE = re.compile(r'^\d+\.\d+$')

# With more than 23 letters, labels are to big for buildbot's popup boxes.
MAX_LABEL_SIZE = 23

# Make sure that a step is not flooded with log lines.
MAX_FAILURE_LOGS = 10

# Factor by which the considered failure for bisection must be faster than the
# ongoing build's total.
BISECT_DURATION_FACTOR = 5

MIPS_TOOLCHAIN = 'mips-2013.11-36-mips-linux-gnu-i686-pc-linux-gnu.tar.bz2'
MIPS_DIR = 'mips-2013.11'

TEST_RUNNER_PARSER = argparse.ArgumentParser()
TEST_RUNNER_PARSER.add_argument('--extra-flags')


class V8Api(recipe_api.RecipeApi):
  BUILDERS = builders.BUILDERS

  # Map of GS archive names to urls.
  GS_ARCHIVES = {
    'android_arm_rel_archive': 'gs://chromium-v8/v8-android-arm-rel',
    'android_arm64_rel_archive': 'gs://chromium-v8/v8-android-arm64-rel',
    'arm_rel_archive': 'gs://chromium-v8/v8-arm-rel',
    'arm_dbg_archive': 'gs://chromium-v8/v8-arm-dbg',
    'linux_rel_archive': 'gs://chromium-v8/v8-linux-rel',
    'linux_dbg_archive': 'gs://chromium-v8/v8-linux-dbg',
    'linux_nosnap_rel_archive': 'gs://chromium-v8/v8-linux-nosnap-rel',
    'linux_nosnap_dbg_archive': 'gs://chromium-v8/v8-linux-nosnap-dbg',
    'linux_x87_nosnap_dbg_archive': 'gs://chromium-v8/v8-linux-x87-nosnap-dbg',
    'linux_swarming_staging_archive':
        'gs://chromium-v8/v8-linux-swarming-staging',
    'linux64_rel_archive': 'gs://chromium-v8/v8-linux64-rel',
    'linux64_dbg_archive': 'gs://chromium-v8/v8-linux64-dbg',
    'linux64_custom_snapshot_dbg_archive':
        'gs://chromium-v8/v8-linux64-custom-snapshot-dbg',
    'mips_rel_archive': 'gs://chromium-v8/v8-mips-rel',
    'mipsel_sim_rel_archive': 'gs://chromium-v8/v8-mipsel-sim-rel',
    'mips64el_sim_rel_archive': 'gs://chromium-v8/v8-mips64el-sim-rel',
    'win32_rel_archive': 'gs://chromium-v8/v8-win32-rel',
    'win32_dbg_archive': 'gs://chromium-v8/v8-win32-dbg',
    'v8_for_dart_archive': 'gs://chromium-v8/v8-for-dart-rel',
  }

  def apply_bot_config(self, builders):
    """Entry method for using the v8 api.

    Requires the presence of a bot_config dict for any main/builder pair.
    This bot_config will be used to refine other api methods.
    """

    mainname = self.m.properties.get('mainname')
    buildername = self.m.properties.get('buildername')
    main_dict = builders.get(mainname, {})
    self.bot_config = main_dict.get('builders', {}).get(buildername)
    assert self.bot_config, (
        'Unrecognized builder name %r for main %r.' % (
            buildername, mainname))

    kwargs = self.bot_config.get('v8_config_kwargs', {})
    self.set_config('v8', optional=True, **kwargs)
    self.m.chromium.set_config('v8', **kwargs)
    self.m.gclient.set_config('v8', **kwargs)

    for c in self.bot_config.get('gclient_apply_config', []):
      self.m.gclient.apply_config(c)
    for c in self.bot_config.get('chromium_apply_config', []):
      self.m.chromium.apply_config(c)
    if self.m.tryserver.is_tryserver:
      self.init_tryserver()
    for c in self.bot_config.get('v8_apply_config', []):
      self.apply_config(c)

    if self.bot_config.get('enable_swarming'):
      self.m.gclient.c.got_revision_mapping['v8/tools/swarming_client'] = (
          'got_swarming_client_revision')

    # FIXME(machenbach): Use a context object that stores the state for each
    # test process. Otherwise it's easy to introduce bugs with multiple test
    # processes and stale context data. E.g. during bisection these values
    # change for tests on rerun.

    # Default failure retry.
    self.rerun_failures_count = 2

    # If tests are run, this value will be set to their total duration.
    self.test_duration_sec = 0

    # Allow overriding the isolate hashes during bisection with the ones that
    # correspond to the build of a bisect step.
    self._isolated_tests_override = None

  @property
  def isolated_tests(self):
    # During bisection, the isolated hashes will be updated with hashes that
    # correspond to the bisect step.
    # TODO(machenbach): Remove pragma as soon as rerun is implemented for
    # swarming.
    if self._isolated_tests_override is not None:  # pragma: no cover
      return self._isolated_tests_override
    return self.m.isolate.isolated_tests

  def testing_random_seed(self):
    """Return a random seed suitable for v8 testing.

    If there are isolate hashes, build a random seed based on the hashes.
    Otherwise use the system's PRNG. This uses a deterministic seed for
    recipe simulation.
    """
    r = random.Random()
    if self.isolated_tests:
      r.seed(tuple(self.isolated_tests))
    elif self._test_data.enabled:
      r.seed(12345)

    seed = 0
    while not seed:
      # Avoid 0 because v8 switches off usage of random seeds when
      # passing 0 and creates a new one.
      seed = r.randint(-2147483648, 2147483647)
    return seed

  def init_tryserver(self):
    self.m.chromium.apply_config('trybot_flavor')

  def checkout(self, revision=None, **kwargs):
    # Set revision for bot_update.
    revision = revision or self.m.properties.get(
        'parent_got_revision', self.m.properties.get('revision', 'HEAD'))
    solution = self.m.gclient.c.solutions[0]
    branch = self.m.properties.get('branch', 'main')
    needs_branch_heads = False
    if RELEASE_BRANCH_RE.match(branch):
      revision = 'refs/branch-heads/%s:%s' % (branch, revision)
      needs_branch_heads = True

    solution.revision = revision
    update_step = self.m.bot_update.ensure_checkout(
        no_shallow=True,
        patch_root=[None, 'v8'][bool(self.m.tryserver.is_tryserver)],
        output_manifest=True,
        with_branch_heads=needs_branch_heads,
        patch_project_roots={'v8': []},
        **kwargs)

    assert update_step.json.output['did_run']

    # Bot_update maintains the properties independent of the UI
    # presentation.
    self.revision = self.m.bot_update.last_returned_properties['got_revision']
    self.revision_cp = (
        self.m.bot_update.last_returned_properties['got_revision_cp'])
    self.revision_number = str(self.m.commit_position.parse_revision(
        self.revision_cp))

    return update_step

  def calculate_patch_base(self):
    """Calculates the latest commit hash that fits the patch."""
    url = ('https://codereview.chromium.org/download/issue%s_%s.diff' %
           (self.m.properties['issue'], self.m.properties['patchset']))
    step_result = self.m.python(
        'Download patch',
        self.package_repo_resource('scripts', 'tools', 'pycurl.py'),
        [url, '--outfile', self.m.raw_io.output()],
        step_test_data=lambda: self.m.raw_io.test_api.output('some patch'),
    )
    return self.m.python(
        name='Calculate patch base',
        script=self.resource('calculate_patch_base.py'),
        args=[
          self.m.raw_io.input(step_result.raw_io.output),
          self.m.path['checkout'],
          self.m.raw_io.output(),
        ],
        step_test_data=lambda: self.m.raw_io.test_api.output('[fitting hsh]'),
    ).raw_io.output

  def set_up_swarming(self):
    if self.bot_config.get('enable_swarming'):
      self.m.isolate.set_isolate_environment(self.m.chromium.c)
      self.m.swarming.check_client_version()
      for key, value in self.bot_config.get(
          'swarming_dimensions', {}).iteritems():
        self.m.swarming.set_default_dimension(key, value)

    self.m.swarming.set_default_dimension('pool', 'Chrome')
    self.m.swarming.add_default_tag('project:v8')
    self.m.swarming.default_hard_timeout = 45 * 60

    self.m.swarming.default_idempotent = True

    if self.m.properties['mainname'] == 'tryserver.v8':
      self.m.swarming.add_default_tag('purpose:pre-commit')
      requester = self.m.properties.get('requester')
      if requester == 'commit-bot@chromium.org':
        self.m.swarming.default_priority = 30
        self.m.swarming.add_default_tag('purpose:CQ')
        blamelist = self.m.properties.get('blamelist')
        if len(blamelist) == 1:
          requester = blamelist[0]
      else:
        self.m.swarming.default_priority = 28
        self.m.swarming.add_default_tag('purpose:ManualTS')
      self.m.swarming.default_user = requester

      patch_project = self.m.properties.get('patch_project')
      if patch_project:
        self.m.swarming.add_default_tag('patch_project:%s' % patch_project)
    else:
      if self.m.properties['mainname'] == 'client.v8':
        self.m.swarming.default_priority = 25
      else:
        # This should be lower than the CQ.
        self.m.swarming.default_priority = 35
      self.m.swarming.add_default_tag('purpose:post-commit')
      self.m.swarming.add_default_tag('purpose:CI')

    # Overwrite defaults with per-bot settings.
    for key, value in self.bot_config.get(
        'swarming_properties', {}).iteritems():
      setattr(self.m.swarming, key, value)

  def runhooks(self, **kwargs):
    env = {}
    if self.c.gyp_env.AR:
      env['AR'] = self.c.gyp_env.AR
    if self.c.gyp_env.CC:
      env['CC'] = self.c.gyp_env.CC
    if self.c.gyp_env.CXX:
      env['CXX'] = self.c.gyp_env.CXX
    if self.c.gyp_env.LINK:
      env['LINK'] = self.c.gyp_env.LINK
    if self.c.gyp_env.RANLIB:
      env['RANLIB'] = self.c.gyp_env.RANLIB
    # TODO(machenbach): Make this the default on windows.
    if self.m.chromium.c.gyp_env.GYP_MSVS_VERSION:
      env['GYP_MSVS_VERSION'] = self.m.chromium.c.gyp_env.GYP_MSVS_VERSION
    self.m.chromium.runhooks(env=env, **kwargs)

  def setup_mips_toolchain(self):
    mips_dir = self.m.path['subordinate_build'].join(MIPS_DIR, 'bin')
    if not self.m.path.exists(mips_dir):
      self.m.gsutil.download_url(
          'gs://chromium-v8/%s' % MIPS_TOOLCHAIN,
          self.m.path['subordinate_build'],
          name='bootstrapping mips toolchain')
      self.m.step('unzipping',
               ['tar', 'xf', MIPS_TOOLCHAIN],
               cwd=self.m.path['subordinate_build'])

    self.c.gyp_env.CC = self.m.path.join(mips_dir, 'mips-linux-gnu-gcc')
    self.c.gyp_env.CXX = self.m.path.join(mips_dir, 'mips-linux-gnu-g++')
    self.c.gyp_env.AR = self.m.path.join(mips_dir, 'mips-linux-gnu-ar')
    self.c.gyp_env.RANLIB = self.m.path.join(mips_dir, 'mips-linux-gnu-ranlib')
    self.c.gyp_env.LINK = self.m.path.join(mips_dir, 'mips-linux-gnu-g++')

  @property
  def bot_type(self):
    return self.bot_config.get('bot_type', 'builder_tester')

  @property
  def should_build(self):
    return self.bot_type in ['builder', 'builder_tester']

  @property
  def should_test(self):
    return self.bot_type in ['tester', 'builder_tester']

  @property
  def should_upload_build(self):
    return (self.bot_type == 'builder' and
            not self.bot_config.get('slim_swarming_builder'))

  @property
  def should_download_build(self):
    return self.bot_type == 'tester'

  @property
  def relative_path_to_d8(self):
    return self.m.path.join('out', self.m.chromium.c.build_config_fs, 'd8')

  def isolate_tests(self):
    if self.bot_config.get('enable_swarming'):
      buildername = self.m.properties['buildername']
      tests_to_isolate = []
      def add_tests_to_isolate(tests):
        for test in tests:
          if not test.swarming:  # pragma: no cover
            # Skip tests that explicitly disable swarming.
            continue
          config = testing.TEST_CONFIGS.get(test.name) or {}

          # Tests either define an explicit isolate target or use the test
          # names for convenience.
          if config.get('isolated_target'):
            tests_to_isolate.append(config['isolated_target'])
          elif config.get('tests'):
            tests_to_isolate.extend(config['tests'])

      # Find tests to isolate on builders.
      for _, _, _, bot_config in iter_builders():
        if bot_config.get('parent_buildername') == buildername:
          add_tests_to_isolate(bot_config.get('tests', []))

      # Find tests to isolate on builder_testers.
      add_tests_to_isolate(self.bot_config.get('tests', []))

      # Add the performance-tests isolate everywhere, where the perf-bot proxy
      # is triggered.
      if self.bot_config.get('triggers_proxy', False):
        tests_to_isolate.append('perf')

      if tests_to_isolate:
        self.m.isolate.isolate_tests(
            self.m.chromium.output_dir,
            targets=sorted(list(set(tests_to_isolate))),
            verbose=True,
            set_swarm_hashes=False,
        )
        if self.should_upload_build:
          self.upload_isolated_json()

  def compile(self, **kwargs):
    self.m.chromium.compile(**kwargs)
    self.isolate_tests()

  # TODO(machenbach): This should move to a dynamorio module as soon as one
  # exists.
  def dr_compile(self):
    self.m.file.makedirs(
      'Create Build Dir',
      self.m.path['subordinate_build'].join('dynamorio', 'build'))
    self.m.step(
      'Configure Release x64 DynamoRIO',
      ['cmake', '..', '-DDEBUG=OFF'],
      cwd=self.m.path['subordinate_build'].join('dynamorio', 'build'),
    )
    self.m.step(
      'Compile Release x64 DynamoRIO',
      ['make', '-j5'],
      cwd=self.m.path['subordinate_build'].join('dynamorio', 'build'),
    )

  @property
  def run_dynamorio(self):
    return self.m.gclient.c.solutions[-1].name == 'dynamorio'

  def upload_build(self, name_suffix='', archive=None):
    archive = archive or self.GS_ARCHIVES[self.bot_config['build_gs_archive']]
    self.m.archive.zip_and_upload_build(
          'package build' + name_suffix,
          self.m.chromium.c.build_config_fs,
          archive,
          src_dir='v8')

  def upload_isolated_json(self):
    archive = self.GS_ARCHIVES[self.bot_config['build_gs_archive']]
    name = self.get_archive_name_pattern(use_swarming=True) % self.revision
    self.m.gsutil.upload(
        self.m.json.input(self.m.isolate.isolated_tests),
        # The gsutil module wants bucket paths without gs:// prefix.
        archive[len('gs://'):],
        name,
        args=['-a', 'public-read'],
    )

  def maybe_create_clusterfuzz_archive(self, update_step):
    if self.bot_config.get('cf_archive_build', False):
      self.m.archive.clusterfuzz_archive(
          revision_dir='v8',
          build_dir=self.m.chromium.c.build_dir.join(
              self.m.chromium.c.build_config_fs),
          update_properties=update_step.presentation.properties,
          gs_bucket=self.bot_config.get('cf_gs_bucket'),
          gs_acl=self.bot_config.get('cf_gs_acl'),
          archive_prefix=self.bot_config.get('cf_archive_name'),
      )

  def download_build(self, name_suffix='', archive=None):
    self.m.file.rmtree(
          'build directory' + name_suffix,
          self.m.chromium.c.build_dir.join(self.m.chromium.c.build_config_fs))

    archive = archive or self.GS_ARCHIVES[self.bot_config['build_gs_archive']]
    self.m.archive.download_and_unzip_build(
          'extract build' + name_suffix,
          self.m.chromium.c.build_config_fs,
          archive,
          src_dir='v8')

  def download_isolated_json(self, revision):
    archive = self.get_archive_url_pattern(use_swarming=True) % revision
    self.m.gsutil.download_url(
        archive,
        self.m.json.output(),
        name='download isolated json',
        step_test_data=lambda: self.m.json.test_api.output(
            {'bot_default': '[dummy hash for bisection]'}),
    )
    step_result = self.m.step.active_result
    self._isolated_tests_override = step_result.json.output

  @property
  def build_output_dir(self):
    return self.m.path.join(
        self.m.chromium.c.build_dir,
        self.m.chromium.c.build_config_fs,
    )

  @property
  def generate_gcov_coverage(self):
    return bool(self.bot_config.get('gcov_coverage_folder'))

  def init_gcov_coverage(self):
    """Delete all gcov counter files."""
    self.m.step(
        'lcov zero counters',
        ['lcov', '--directory', self.build_output_dir, '--zerocounters'],
    )

  def upload_gcov_coverage_report(self):
    """Capture coverage data and upload a report."""
    coverage_dir = self.m.path.mkdtemp('gcov_coverage')
    report_dir = self.m.path.mkdtemp('gcov_coverage_html')
    output_file = self.m.path.join(coverage_dir, 'app.info')

    # Capture data from gcda and gcno files.
    self.m.step(
        'lcov capture',
        [
          'lcov',
          '--directory', self.build_output_dir,
          '--capture',
          '--output-file', output_file,
        ],
    )

    # Remove unwanted data.
    self.m.step(
        'lcov remove',
        [
          'lcov',
          '--directory', self.build_output_dir,
          '--remove', output_file,
          'third_party/*',
          'testing/gtest/*',
          'testing/gmock/*',
          '/usr/include/*',
          '--output-file', output_file,
        ],
    )

    # Generate html report into a temp folder.
    self.m.step(
        'genhtml',
        [
          'genhtml',
          '--output-directory', report_dir,
          output_file,
        ],
    )

    # Upload report to google storage.
    dest = '%s/%s' % (self.bot_config['gcov_coverage_folder'], self.revision)
    result = self.m.gsutil(
        [
          '-m', 'cp', '-a', 'public-read', '-R', report_dir,
          'gs://chromium-v8/%s' % dest,
        ],
        'coverage report',
    )
    result.presentation.links['report'] = (
      'https://storage.googleapis.com/chromium-v8/%s/index.html' % dest)

  @property
  def generate_sanitizer_coverage(self):
    return bool(self.bot_config.get('sanitizer_coverage_folder'))

  def create_coverage_context(self):
    if self.generate_sanitizer_coverage:
      return testing.SanitizerCoverageContext(self.m, self)
    else:
      return testing.NULL_COVERAGE

  def create_test(self, test):
    """Wrapper that allows to shortcut common tests with their names.

    Returns: A runnable test instance.
    """
    return testing.create_test(test, self.m, self)

  def create_tests(self):
    return [self.create_test(t) for t in self.bot_config.get('tests', [])]

  def is_pure_swarming_tester(self, tests):
    return (self.bot_type == 'tester' and
            self.bot_config.get('enable_swarming') and
            all(map(lambda x: x.uses_swarming, tests)))

  def runtests(self, tests):
    if self.extra_flags:
      result = self.m.step('Customized run with extra flags', cmd=None)
      result.presentation.step_text += ' '.join(self.extra_flags)
      assert all(re.match(r'[\w\-]*', x) for x in self.extra_flags), (
          'no special characters allowed in extra flags')

    start_time_sec = self.m.time.time()
    test_results = testing.TestResults.empty()

    # Apply test filter.
    # TODO(machenbach): Track also the number of tests that ran and throw an
    # error if the overall number of tests from all steps was zero.
    tests = [t for t in tests if t.apply_filter()]

    swarming_tests = [t for t in tests if t.uses_swarming]
    non_swarming_tests = [t for t in tests if not t.uses_swarming]
    failed_tests = []

    # Creates a coverage context if coverage is tracked. Null object otherwise.
    coverage_context = self.create_coverage_context()

    # Make sure swarming triggers come first.
    # TODO(machenbach): Port this for rerun for bisection.
    for t in swarming_tests + non_swarming_tests:
      try:
        t.pre_run(coverage_context=coverage_context)
      except self.m.step.InfraFailure:  # pragma: no cover
        raise
      except self.m.step.StepFailure:  # pragma: no cover
        failed_tests.append(t)

    # Setup initial zero coverage after all swarming jobs are triggered.
    coverage_context.setup()

    # Make sure non-swarming tests are run before swarming results are
    # collected.
    for t in non_swarming_tests + swarming_tests:
      try:
        test_results += t.run(coverage_context=coverage_context)
      except self.m.step.InfraFailure:  # pragma: no cover
        raise
      except self.m.step.StepFailure:  # pragma: no cover
        failed_tests.append(t)

    # Upload accumulated coverage data.
    coverage_context.maybe_upload()

    if failed_tests:
      failed_tests_names = [t.name for t in failed_tests]
      raise self.m.step.StepFailure(
          '%d tests failed: %r' % (len(failed_tests), failed_tests_names))
    self.test_duration_sec = self.m.time.time() - start_time_sec
    return test_results

  def maybe_bisect(self, test_results):
    """Build-local bisection for one failure."""
    # Don't activate for branch or fyi bots.
    if self.m.properties['mainname'] != 'client.v8':
      return

    if self.bot_config.get('disable_auto_bisect'):  # pragma: no cover
      return

    # Only bisect over failures not flakes. Rerun only the fastest test.
    try:
      failure = min(test_results.failures, key=lambda r: r.duration)
    except ValueError:
      return

    # Only bisect if the fastest failure is significantly faster than the
    # ongoing build's total.
    duration_factor = self.m.properties.get(
        'bisect_duration_factor', BISECT_DURATION_FACTOR)
    if (failure.duration * duration_factor > self.test_duration_sec):
      step_result = self.m.step(
          'Bisection disabled - test too slow', cmd=None)
      return

    # Don't retry failures during bisection.
    self.rerun_failures_count = 0

    # Suppress using shards to be able to rerun single tests.
    self.c.testing.may_shard = False

    # Only rebuild the target of the test to retry. Works only with ninja.
    targets = None
    if 'ninja' in self.m.chromium.c.gyp_env.GYP_GENERATORS:
      targets = [failure.failure_dict.get('target_name', 'All')]

    test = self.create_test(failure.test_step_config)
    def test_func(revision):
      return test.rerun(failure_dict=failure.failure_dict)

    def is_bad(revision):
      with self.m.step.nest('Bisect ' + revision[:8]):
        if not self.is_pure_swarming_tester([test]):
          self.checkout(revision, update_presentation=False)
        if self.bot_type == 'builder_tester':
          self.runhooks()
          self.compile(targets=targets)
        elif self.bot_type == 'tester':
          if test.uses_swarming:
            self.download_isolated_json(revision)
          else:
            self.download_build()
        else:  # pragma: no cover
          raise self.m.step.InfraFailure(
              'Bot type %s not supported.' % self.bot_type)
        result = test_func(revision)
        if result.infra_failures:  # pragma: no cover
          raise self.m.step.InfraFailure(
              'Cannot continue bisection due to infra failures.')
        return result.failures

    with self.m.step.nest('Bisect'):
      # Setup bisection range ("from" exclusive).
      latest_previous, bisect_range = self.get_change_range()
      if len(bisect_range) <= 1:
        self.m.step('disabled - less than two changes', cmd=None)
        return

      if self.bot_type == 'tester':
        # Filter the bisect range to the revisions for which isolate hashes or
        # archived builds are available, depending on whether swarming is used
        # or not.
        available_bisect_range = self.get_available_range(
            bisect_range, test.uses_swarming)
      else:
        available_bisect_range = bisect_range

    if is_bad(latest_previous):
      # If latest_previous is already "bad", the test failed before the current
      # build's change range, i.e. it is a recurring failure.
      # TODO: Try to be smarter here, fetch the build data from the previous
      # one or two builds and check if the failure happened in revision
      # latest_previous. Otherwise, the cost of calling is_bad is as much as
      # one bisect step.
      step_result = self.m.step(
          'Bisection disabled - recurring failure', cmd=None)
      step_result.presentation.status = self.m.step.WARNING
      return

    # Log available revisions to ease debugging.
    self.log_available_range(available_bisect_range)

    culprit = bisection.keyed_bisect(available_bisect_range, is_bad)
    culprit_range = self.calc_missing_values_in_sequence(
        bisect_range,
        available_bisect_range,
        culprit,
    )
    self.report_culprits(culprit_range)

  @staticmethod
  def format_duration(duration_in_seconds):
    duration = datetime.timedelta(seconds=duration_in_seconds)
    time = (datetime.datetime.min + duration).time()
    return time.strftime('%M:%S:') + '%03i' % int(time.microsecond / 1000)

  def _command_results_text(self, results, flaky):
    """Returns log lines for all results of a unique command."""
    assert results
    lines = []

    # Add common description for multiple runs.
    flaky_suffix = ' (flaky in a repeated run)' if flaky else ''
    lines.append('Test: %s%s' % (results[0]['name'], flaky_suffix))
    lines.append('Flags: %s' % ' '.join(results[0]['flags']))
    lines.append('Command: %s' % results[0]['command'])
    lines.append('')

    # Add results for each run of a command.
    for result in sorted(results, key=lambda r: int(r['run'])):
      lines.append('Run #%d' % int(result['run']))
      lines.append('Exit code: %s' % result['exit_code'])
      lines.append('Result: %s' % result['result'])
      if result.get('expected'):
        lines.append('Expected outcomes: %s' % ", ".join(result['expected']))
      lines.append('Duration: %s' % V8Api.format_duration(result['duration']))
      lines.append('')
      if result['stdout']:
        lines.append('Stdout:')
        lines.extend(result['stdout'].splitlines())
        lines.append('')
      if result['stderr']:
        lines.append('Stderr:')
        lines.extend(result['stderr'].splitlines())
        lines.append('')
    return lines

  def _duration_results_text(self, test):
    return [
      'Test: %s' % test['name'],
      'Flags: %s' % ' '.join(test['flags']),
      'Command: %s' % test['command'],
      'Duration: %s' % V8Api.format_duration(test['duration']),
    ]

  def _update_durations(self, output, presentation):
    # Slowest tests duration summary.
    lines = []
    for test in output['slowest_tests']:
      lines.append(
          '%s %s' %(V8Api.format_duration(test['duration']), test['name']))
    # Slowest tests duration details.
    lines.extend(['', 'Details:', ''])
    for test in output['slowest_tests']:
      lines.extend(self._duration_results_text(test))
    presentation.logs['durations'] = lines

  def _get_failure_logs(self, output, failure_factory):
    def all_same(items):
      return all(x == items[0] for x in items)

    if not output['results']:
      return {}, [], {}, []

    unique_results = {}
    for result in output['results']:
      # Use test base name as UI label (without suite and directory names).
      label = result['name'].split('/')[-1]
      # Truncate the label if it is still too long.
      if len(label) > MAX_LABEL_SIZE:
        label = label[:MAX_LABEL_SIZE - 2] + '..'
      # Group tests with the same label (usually the same test that ran under
      # different configurations).
      unique_results.setdefault(label, []).append(result)

    failure_log = {}
    flake_log = {}
    failures = []
    flakes = []
    for label in sorted(unique_results.keys()[:MAX_FAILURE_LOGS]):
      failure_lines = []
      flake_lines = []

      # Group results by command. The same command might have run multiple
      # times to detect flakes.
      results_per_command = {}
      for result in unique_results[label]:
        results_per_command.setdefault(result['command'], []).append(result)

      for command in results_per_command:
        # Determine flakiness. A test is flaky if not all results from a unique
        # command are the same (e.g. all 'FAIL').
        if all_same(map(lambda x: x['result'], results_per_command[command])):
          # This is a failure. Only add the data of the first run to the final
          # test results, as rerun data is not important for bisection.
          failure = results_per_command[command][0]
          failures.append(failure_factory(failure, failure['duration']))
          failure_lines += self._command_results_text(
              results_per_command[command], False)
        else:
          # This is a flake. Only add the data of the first run to the final
          # test results, as rerun data is not important for bisection.
          flake = results_per_command[command][0]
          flakes.append(failure_factory(flake, flake['duration']))
          flake_lines += self._command_results_text(
              results_per_command[command], True)

      if failure_lines:
        failure_log[label] = failure_lines
      if flake_lines:
        flake_log[label] = flake_lines

    return failure_log, failures, flake_log, flakes

  def _update_failure_presentation(self, log, failures, presentation):
    for label in sorted(log):
      presentation.logs[label] = log[label]

    if failures:
      # Number of failures.
      presentation.step_text += ('failures: %d<br/>' % len(failures))

  @property
  def extra_flags(self):
    extra_flags = self.m.properties.get('extra_flags', '')
    if isinstance(extra_flags, basestring):
      extra_flags = extra_flags.split()
    assert isinstance(extra_flags, list) or isinstance(extra_flags, tuple)
    return list(extra_flags)

  def _with_extra_flags(self, args):
    """Returns: the arguments with additional extra flags inserted.

    Extends a possibly existing extra flags option.
    """
    if not self.extra_flags:
      return args

    options, args = TEST_RUNNER_PARSER.parse_known_args(args)

    if options.extra_flags:
      new_flags = [options.extra_flags] + self.extra_flags
    else:
      new_flags = self.extra_flags

    args.extend(['--extra-flags', ' '.join(new_flags)])
    return args

  @property
  def test_filter(self):
    return [f for f in self.m.properties.get('testfilter', [])
            if f != 'defaulttests']

  def _applied_test_filter(self, test):
    """Returns: the list of test filters that match a test configuration."""
    # V8 test filters always include the full suite name, followed
    # by more specific paths and possibly ending with a glob, e.g.:
    # 'mjsunit/regression/prefix*'.
    return [f for f in self.test_filter
              for t in test.get('suite_mapping', test['tests'])
              if f.startswith(t)]

  def _setup_test_runner(self, test, applied_test_filter):
    env = {}
    full_args = [
      '--progress=verbose',
      '--mode', self.m.chromium.c.build_config_fs,
      '--arch', self.m.chromium.c.gyp_env.GYP_DEFINES['v8_target_arch'],
      '--outdir', self.m.path.split(self.m.chromium.c.build_dir)[-1],
      '--buildbot',
      '--timeout=200',
    ]

    # On reruns, there's a fixed random seed set in the test configuration.
    if '--random-seed' not in test.get('test_args', []):
      full_args.append('--random-seed=%d' % self.testing_random_seed())

    # Either run tests as specified by the filter (trybots only) or as
    # specified by the test configuration.
    if applied_test_filter:
      full_args += applied_test_filter
    else:
      full_args += list(test['tests'])

    # Add test-specific test arguments.
    full_args += test.get('test_args', [])

    # Add builder-specific test arguments.
    full_args += self.c.testing.test_args

    full_args = self._with_extra_flags(full_args)

    if self.run_dynamorio:
      drrun = self.m.path['subordinate_build'].join(
          'dynamorio', 'build', 'bin64', 'drrun')
      full_args += [
        '--command_prefix',
        '%s -reset_every_nth_pending 0 --' % drrun,
      ]

    # Indicate whether DCHECKs were enabled.
    if self.m.chromium.c.gyp_env.GYP_DEFINES.get('dcheck_always_on') == 1:
      full_args.append('--dcheck-always-on')

    for gyp_flag in ['asan', 'cfi_vptr', 'tsan', 'msan']:
      if self.m.chromium.c.gyp_env.GYP_DEFINES.get(gyp_flag) == 1:
        full_args.append('--%s' % gyp_flag.replace('_', '-'))

    full_args += [
      '--rerun-failures-count=%d' % self.rerun_failures_count,
    ]
    return full_args, env

  def verify_cq_integrity(self):
    # TODO(machenbach): Remove this as soon as crbug.com/487822 is resolved.
    if self.test_filter:
      result = self.m.step('CQ integrity - used testfilter', cmd=None)
      result.presentation.status = self.m.step.FAILURE
    if self.extra_flags:
      result = self.m.step('CQ integrity - used extra flags', cmd=None)
      result.presentation.status = self.m.step.FAILURE

  def maybe_trigger(self, **additional_properties):
    triggers = self.bot_config.get('triggers', [])
    triggers_proxy = self.bot_config.get('triggers_proxy', False)
    if triggers or triggers_proxy:
      properties = {
        'parent_got_revision': self.revision,
        'parent_got_revision_cp': self.revision_cp,
      }
      if self.m.tryserver.is_tryserver:
        properties.update(
          category=self.m.properties.get('category', 'manual_ts'),
          issue=self.m.properties['issue'],
          main=str(self.m.properties['main']),
          patch_project=str(self.m.properties['patch_project']),
          patch_storage=str(self.m.properties['patch_storage']),
          patchset=str(self.m.properties['patchset']),
          reason=str(self.m.properties.get('reason', 'ManualTS')),
          requester=str(self.m.properties['requester']),
          # On tryservers, set revision to the same as on the current bot,
          # as CQ expects builders and testers to match the revision field.
          revision=str(self.m.properties.get('revision', 'HEAD')),
          rietveld=str(self.m.properties['rietveld']),
        )
      else:
        # On non-tryservers, we can set the revision to whatever the
        # triggering builder checked out.
        properties['revision'] = self.revision

      # TODO(machenbach): Also set meaningful buildbucket tags of triggering
      # parent.

      swarm_hashes = self.m.isolate.isolated_tests
      if swarm_hashes:
        properties['swarm_hashes'] = swarm_hashes
      properties.update(**additional_properties)
      self.m.trigger(*[{
        'builder_name': builder_name,
        'properties': properties,
      } for builder_name in triggers])

      if triggers_proxy:
        proxy_properties = {
          'archive': self.GS_ARCHIVES[self.bot_config['build_gs_archive']],
        }
        proxy_properties.update(properties)
        self.m.trigger(*[{
          'builder_name': 'v8_trigger_proxy',
          'bucket': 'main.internal.client.v8',
          'properties': proxy_properties,
          'buildbot_changes': [{
            'author': 'trigger_proxy',
            'revision': self.revision,
          }]
        }])

  def get_change_range(self):
    if self.m.properties.get('override_changes'):
      # This can be used for manual testing or on a staging builder that
      # simulates a change range.
      changes = self.m.properties['override_changes']
      step_result = self.m.step('Override changes', cmd=None)
      step_result.presentation.logs['changes'] = self.m.json.dumps(
        changes, indent=2).splitlines()
    else:
      url = '%sjson/builders/%s/builds/%s/source_stamp' % (
          self.m.properties['buildbotURL'],
          urllib.quote(self.m.properties['buildername']),
          str(self.m.properties['buildnumber']),
      )
      step_result = self.m.python(
          'Fetch changes',
          self.package_repo_resource('scripts', 'tools', 'pycurl.py'),
          [
            url,
            '--outfile',
            self.m.json.output(),
          ],
          step_test_data=lambda: self.test_api.example_buildbot_changes(),
      )
      changes = step_result.json.output['changes']

    assert changes
    first_change = changes[0]['revision']
    last_change = changes[-1]['revision']

    # Commits is a list of gitiles commit dicts in reverse chronological order.
    commits, _ = self.m.gitiles.log(
        url=V8_URL,
        ref='%s~2..%s' % (first_change, last_change),
        limit=100,
        step_name='Get change range',
        step_test_data=lambda: self.test_api.example_bisection_range()
    )

    # We get minimum two commits when the first and last commit are equal (i.e.
    # there was only one commit C). Commits will contain the latest previous
    # commit and C.
    assert len(commits) > 1

    return (
        # Latest previous.
        commits[-1]['commit'],
        # List of commits oldest -> newest, without the latest previous.
        [commit['commit'] for commit in reversed(commits[:-1])],
    )

  def get_archive_name_pattern(self, use_swarming):
    # For tests run on swarming, only lookup the json file with the isolate
    # hashes.
    suffix = 'json' if use_swarming else 'zip'

    return 'full-build-%s_%%s.%s' % (
        self.m.archive.legacy_platform_name(),
        suffix,
    )

  def get_archive_url_pattern(self, use_swarming):
    return '%s/%s' % (
        self.GS_ARCHIVES[self.bot_config['build_gs_archive']],
        self.get_archive_name_pattern(use_swarming),
    )

  def get_available_range(self, bisect_range, use_swarming=False):
    assert self.bot_type == 'tester'
    archive_url_pattern = self.get_archive_url_pattern(use_swarming)
    # TODO(machenbach): Maybe parallelize this in a wrapper script.
    args = ['ls']
    available_range = []
    # Check all builds except the last as we already know it is "bad".
    for r in bisect_range[:-1]:
      step_result = self.m.gsutil(
          args + [archive_url_pattern % r],
          name='check build %s' % r[:8],
          # Allow failures, as the tool will formally fail for any absent file.
          ok_ret='any',
          stdout=self.m.raw_io.output(),
          step_test_data=lambda: self.test_api.example_available_builds(r),
      )
      if r in step_result.stdout.strip():
        available_range.append(r)

    # Always keep the latest revision in the range. The latest build is
    # assumed to be "bad" and won't be tested again.
    available_range.append(bisect_range[-1])
    return available_range

  def calc_missing_values_in_sequence(
        self, sequence, subsequence, value):
    """Calculate a list of missing values from a subsequence.

    Args:
      sequence: The complete sequence including all values.
      subsequence: A subsequence from the sequence above.
      value: An element from subsequence.
    Returns: A subsequence from sequence [a..b], where b is the value and
             for all x in a..b-1 holds x not in subsequence. Also
             a-1 is either in subsequence or value was the first
             element in subsequence.
    """
    from_index = 0
    to_index = sequence.index(value) + 1
    index_on_subsequence = subsequence.index(value)
    if index_on_subsequence > 0:
      # Value is not the first element in subsequence.
      previous = subsequence[index_on_subsequence - 1]
      from_index = sequence.index(previous) + 1
    return sequence[from_index:to_index]

  def log_available_range(self, available_bisect_range):
    step_result = self.m.step('Available range', cmd=None)
    for revision in available_bisect_range:
      step_result.presentation.links[revision[:8]] = COMMIT_TEMPLATE % revision

  def report_culprits(self, culprit_range):
    assert culprit_range
    if len(culprit_range) > 1:
      text = 'Suspecting multiple commits'
    else:
      text = 'Suspecting %s' % culprit_range[0][:8]

    step_result = self.m.step(text, cmd=None)
    for culprit in culprit_range:
      step_result.presentation.links[culprit[:8]] = COMMIT_TEMPLATE % culprit
