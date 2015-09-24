# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import math
import re
import urllib

from recipe_engine.types import freeze
from recipe_engine import recipe_api
from . import bisection
from . import builders


COMMIT_TEMPLATE = 'https://chromium.googlesource.com/v8/v8/+/%s'

# Regular expressions for v8 branch names.
RELEASE_BRANCH_RE = re.compile(r'^\d+\.\d+$')
ROLL_BRANCH_RE = re.compile(r'^\d+\.\d+\.\d+$')

# With more than 23 letters, labels are to big for buildbot's popup boxes.
MAX_LABEL_SIZE = 23

# Make sure that a step is not flooded with log lines.
MAX_FAILURE_LOGS = 10

# Factor by which the considered failure for bisection must be faster than the
# ongoing build's total.
BISECT_DURATION_FACTOR = 5

MIPS_TOOLCHAIN = 'mips-2013.11-36-mips-linux-gnu-i686-pc-linux-gnu.tar.bz2'
MIPS_DIR = 'mips-2013.11'

TEST_CONFIGS = freeze({
  'benchmarks': {
    'name': 'Benchmarks',
    'tests': ['benchmarks'],
    'test_args': ['--download-data'],
  },
  'mjsunit': {
    'name': 'Mjsunit',
    'tests': ['mjsunit'],
    'add_flaky_step': True,
  },
  'mozilla': {
    'name': 'Mozilla',
    'tests': ['mozilla'],
    'gclient_apply_config': ['mozilla_tests'],
  },
  'optimize_for_size': {
    'name': 'OptimizeForSize',
    'tests': ['optimize_for_size'],
    'add_flaky_step': True,
    'test_args': ['--no-variants', '--extra-flags=--optimize-for-size'],
  },
  'simdjs_small': {
    'name': 'SimdJs - small',
    'tests': ['simdjs/shell_test_runner'],
    'test_args': ['--download-data'],
  },
  'simdjs': {
    'name': 'SimdJs - all',
    'tests': ['simdjs'],
    'test_args': ['--download-data'],
  },
  'test262': {
    'name': 'Test262 - no variants',
    'tests': ['test262'],
    'test_args': ['--no-variants', '--download-data'],
  },
  'test262_variants': {
    'name': 'Test262',
    'tests': ['test262'],
    'test_args': ['--download-data'],
  },
  'test262_es6': {
    'name': 'Test262-es6 - no variants',
    'tests': ['test262-es6'],
    'test_args': ['--no-variants', '--download-data'],
  },
  'test262_es6_variants': {
    'name': 'Test262-es6',
    'tests': ['test262-es6'],
    'test_args': ['--download-data'],
  },
  'unittests': {
    'name': 'Unittests',
    'tests': ['unittests'],
  },
  'v8testing': {
    'name': 'Check',
    'tests': ['default'],
    'add_flaky_step': True,
  },
  'webkit': {
    'name': 'Webkit',
    'tests': ['webkit'],
    'add_flaky_step': True,
  },
})


class BaseTest(object):
  def __init__(self, name, api, v8):
    self.name = name
    self.api = api
    self.v8 = v8

  def run(self, **kwargs):  # pragma: no cover
    raise NotImplementedError()

  def rerun(self, failure_dict, **kwargs):  # pragma: no cover
    raise NotImplementedError()

  def gclient_apply_config(self):
    pass


class V8Test(BaseTest):
  def run(self, test_config=None, **kwargs):
    return self.v8.runtest(
        test_config or TEST_CONFIGS[self.name],
        failure_factory=Failure.factory_func(self.name),
        **kwargs
    )

  def rerun(self, failure_dict, **kwargs):
    # Make sure bisection is only activated on builders that give enough
    # information to retry.
    assert failure_dict.get('variant')
    assert failure_dict.get('random_seed')

    # Filter variant manipulation and data downloading from test arguments.
    # We'll specify exactly the variant which failed. Downloading is not
    # necessary as this is a rerun and all test data is already downloaded
    # in the original run.
    orig_args = list(filter(
        lambda x: x not in ['--no-variants', '--download-data'],
        TEST_CONFIGS[self.name].get('test_args', []),
    ))
    new_args = [
      '--variants', failure_dict['variant'],
      '--random-seed', failure_dict['random_seed'],
    ]
    rerun_config = {
      'name': 'Retry',
      'tests': [failure_dict['name']],
      'test_args' : orig_args + new_args,
    }
    return self.run(test_config=rerun_config, **kwargs)

  def gclient_apply_config(self):
    for c in TEST_CONFIGS[self.name].get('gclient_apply_config', []):
      self.api.gclient.apply_config(c)


class V8Presubmit(BaseTest):
  def run(self, **kwargs):
    self.v8.presubmit()
    return TestResults.empty()


class V8CheckInitializers(BaseTest):
  def run(self, **kwargs):
    self.v8.check_initializers()
    return TestResults.empty()


class V8Fuzzer(BaseTest):
  def run(self, **kwargs):
    self.v8.fuzz()
    return TestResults.empty()


class V8DeoptFuzzer(BaseTest):
  def run(self, **kwargs):
    self.v8.deopt_fuzz()
    return TestResults.empty()


class V8GCMole(BaseTest):
  def run(self, **kwargs):
    self.v8.gc_mole('ia32', 'x64', 'arm', 'arm64')
    return TestResults.empty()


class V8SimpleLeakCheck(BaseTest):
  def run(self, **kwargs):
    self.v8.simple_leak_check()
    return TestResults.empty()


V8_NON_STANDARD_TESTS = freeze({
  'deopt': V8DeoptFuzzer,
  'fuzz': V8Fuzzer,
  'gcmole': V8GCMole,
  'presubmit': V8Presubmit,
  'simpleleak': V8SimpleLeakCheck,
  'v8initializers': V8CheckInitializers,
})


class Failure(object):
  def __init__(self, test_config, failure_dict, duration):
    self.test_config = test_config
    self.failure_dict = failure_dict
    self.duration = duration

  @staticmethod
  def factory_func(test_config):
    def create(failure_dict, duration):
      return Failure(test_config, failure_dict, duration)
    return create


class TestResults(object):
  def __init__(self, failures, flakes, infra_failures):
    self.failures = failures
    self.flakes = flakes
    self.infra_failures = infra_failures

  @staticmethod
  def empty():
    return TestResults([], [], [])

  @property
  def is_negative(self):
    return bool(self.failures or self.flakes or self.infra_failures)

  def __add__(self, other):
    return TestResults(
        self.failures + other.failures,
        self.flakes + other.flakes,
        self.infra_failures + other.infra_failures,
    )


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
    'linux_x32_nosnap_dbg_archive': 'gs://chromium-v8/v8-linux-x32-nosnap-dbg',
    'linux_x87_nosnap_dbg_archive': 'gs://chromium-v8/v8-linux-x87-nosnap-dbg',
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

    Requires the presence of a bot_config dict for any master/builder pair.
    This bot_config will be used to refine other api methods.
    """

    mastername = self.m.properties.get('mastername')
    buildername = self.m.properties.get('buildername')
    master_dict = builders.get(mastername, {})
    self.bot_config = master_dict.get('builders', {}).get(buildername)
    assert self.bot_config, (
        'Unrecognized builder name %r for master %r.' % (
            buildername, mastername))

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
    # Test-specific configurations.
    for t in self.bot_config.get('tests', []):
      self.create_test(t).gclient_apply_config()
    # Initialize perf_dashboard api if any perf test should run.
    self.m.perf_dashboard.set_default_config()

    # Default failure retry.
    self.rerun_failures_count = 2

    # If tests are run, this value will be set to their total duration.
    self.test_duration_sec = 0

  def set_bot_config(self, bot_config):
    """Set bot configuration for testing only."""
    self.bot_config = bot_config

  def init_tryserver(self):
    self.m.chromium.apply_config('trybot_flavor')
    self.apply_config('trybot_flavor')

  def checkout(self, revision=None, **kwargs):
    # Set revision for bot_update.
    revision = revision or self.m.properties.get(
        'parent_got_revision', self.m.properties.get('revision', 'HEAD'))
    solution = self.m.gclient.c.solutions[0]
    branch = self.m.properties.get('branch', 'master')
    needs_branch_heads = False
    if RELEASE_BRANCH_RE.match(branch):
      revision = 'refs/branch-heads/%s:%s' % (branch, revision)
      needs_branch_heads = True
    elif ROLL_BRANCH_RE.match(branch):
      revision = 'refs/heads/%s:%s' % (branch, revision)

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
    self.revision = self.m.bot_update.properties['got_revision']
    self.revision_cp = self.m.bot_update.properties['got_revision_cp']
    self.revision_number = str(self.m.commit_position.parse_revision(
        self.revision_cp))

    return update_step

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
    mips_dir = self.m.path['slave_build'].join(MIPS_DIR, 'bin')
    if not self.m.path.exists(mips_dir):
      self.m.gsutil.download_url(
          'gs://chromium-v8/%s' % MIPS_TOOLCHAIN,
          self.m.path['slave_build'],
          name='bootstrapping mips toolchain')
      self.m.step('unzipping',
               ['tar', 'xf', MIPS_TOOLCHAIN],
               cwd=self.m.path['slave_build'])

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
    return self.bot_type == 'builder'

  @property
  def should_download_build(self):
    return self.bot_type == 'tester'

  @property
  def perf_tests(self):
    return self.bot_config.get('perf', [])

  def compile(self, **kwargs):
    self.m.chromium.compile(**kwargs)

  # TODO(machenbach): This should move to a dynamorio module as soon as one
  # exists.
  def dr_compile(self):
    self.m.file.makedirs(
      'Create Build Dir',
      self.m.path['slave_build'].join('dynamorio', 'build'))
    self.m.step(
      'Configure Release x64 DynamoRIO',
      ['cmake', '..', '-DDEBUG=OFF'],
      cwd=self.m.path['slave_build'].join('dynamorio', 'build'),
    )
    self.m.step(
      'Compile Release x64 DynamoRIO',
      ['make', '-j5'],
      cwd=self.m.path['slave_build'].join('dynamorio', 'build'),
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

  # TODO(machenbach): Pass api already in constructor to avoid redundant api
  # parameter passing later.
  def create_test(self, test):
    """Wrapper that allows to shortcut common tests with their names.

    Returns: A runnable test instance.
    """
    return V8_NON_STANDARD_TESTS.get(test, V8Test)(test, self.m, self)

  def runtests(self):
    start_time_sec = self.m.time.time()
    test_results = TestResults.empty()
    for t in self.bot_config.get('tests', []):
      test_results += self.create_test(t).run()
    self.test_duration_sec = self.m.time.time() - start_time_sec
    return test_results

  def maybe_bisect(self, test_results):
    """Build-local bisection for one failure."""
    # Don't activate for branch or fyi bots.
    if self.m.properties['mastername'] != 'client.v8':
      return

    # Only bisect over failures not flakes. Rerun only the fastest test.
    try:
      failure = min(test_results.failures, key=lambda r: r.duration)
    except ValueError:
      return

    # Only bisect if the fastest failure is significantly faster than the
    # ongoing build's total.
    if failure.duration * BISECT_DURATION_FACTOR > self.test_duration_sec:
      step_result = self.m.python.inline(
          'Bisection disabled - test too slow', '# Empty program')
      return

    # Don't retry failures during bisection.
    self.rerun_failures_count = 0

    # Suppress using shards to be able to rerun single tests.
    self.c.testing.may_shard = False

    # Only rebuild the target of the test to retry. Works only with ninja.
    targets = None
    if 'ninja' in self.m.chromium.c.gyp_env.GYP_GENERATORS:
      targets = [failure.failure_dict.get('target_name', 'All')]

    test = self.create_test(failure.test_config)
    def test_func(revision):
      return test.rerun(
          failure_dict=failure.failure_dict,
          # Don't differentiate between flaky and non-flaky tests. 
          add_flaky_step_override=False,
      )

    def is_bad(revision):
      with self.m.step.nest('Bisect ' + revision[:8]):
        self.checkout(revision, update_presentation=False)
        if self.bot_type == 'builder_tester':
          self.runhooks()
          self.compile(targets=targets)
        elif self.bot_type == 'tester':
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
      from_change, to_change, nchanges = self.get_change_range()
      if nchanges <= 1:
        self.m.step('disabled - less than two changes', cmd=None)
        return
      assert from_change
      assert to_change

      # Initialize bisection range.
      step_result = self.m.git(
        'log', '%s..%s' % (from_change, to_change), '--format=%H',
        name='Fetch range',
        cwd=self.m.path['checkout'],
        stdout=self.m.raw_io.output(),
        step_test_data=lambda: self.test_api.example_bisection_range()
      )
      bisect_range = list(reversed(step_result.stdout.strip().splitlines()))
      
      if self.bot_type == 'tester':
        # Filter the bisect range to the revisions for which builds are
        # available.
        available_bisect_range = self.get_available_range(bisect_range)
      else:
        available_bisect_range = bisect_range

    if is_bad(from_change):
      # If from_change is already "bad", the test failed before the current
      # build's change range, i.e. it is a recurring failure.
      # TODO: Try to be smarter here, fetch the build data from the previous
      # one or two builds and check if the failure happened in revision
      # from_change. Otherwise, the cost of calling is_bad is as much as one
      # bisect step.
      step_result = self.m.python.inline(
          'Bisection disabled - recurring failure', '# Empty program')
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

  def presubmit(self):
    self.m.python(
      'Presubmit',
      self.m.path['checkout'].join('tools', 'presubmit.py'),
      cwd=self.m.path['checkout'],
    )

  def check_initializers(self):
    self.m.step(
      'Static-Initializers',
      ['bash',
       self.m.path['checkout'].join('tools', 'check-static-initializers.sh'),
       self.m.path.join(self.m.path.basename(self.m.chromium.c.build_dir),
                        self.m.chromium.c.build_config_fs,
                        'd8')],
      cwd=self.m.path['checkout'],
    )

  def fuzz(self):
    assert self.m.chromium.c.HOST_PLATFORM == 'linux'
    try:
      self.m.step(
        'Fuzz',
        ['bash',
         self.m.path['checkout'].join('tools', 'fuzz-harness.sh'),
         self.m.path.join(self.m.path.basename(self.m.chromium.c.build_dir),
                          self.m.chromium.c.build_config_fs,
                          'd8')],
        cwd=self.m.path['checkout'],
        stdout=self.m.raw_io.output(),
      )
    except self.m.step.StepFailure as e:
      # Check if the fuzzer left a fuzz archive and upload to GS.
      match = re.search(r'^Creating archive (.*)$', e.result.stdout, re.M)
      if match:
        self.m.gsutil.upload(
            self.m.path['checkout'].join(match.group(1)),
            'chromium-v8',
            self.m.path.join('fuzzer-archives', match.group(1)),
        )
      else:  # pragma: no cover
        self.m.step('No fuzzer archive found.', cmd=None)
      raise e


  def gc_mole(self, *archs):
    # TODO(machenbach): Make gcmole work with absolute paths. Currently, a
    # particular clang version is installed on one slave in '/b'.
    env = {
      'CLANG_BIN': (
        self.m.path.join('..', '..', '..', '..', '..', 'gcmole', 'bin')
      ),
      'CLANG_PLUGINS': (
        self.m.path.join('..', '..', '..', '..', '..', 'gcmole')
      ),
    }
    for arch in archs:
      self.m.step(
        'GCMole %s' % arch,
        ['lua', self.m.path.join('tools', 'gcmole', 'gcmole.lua'), arch],
        cwd=self.m.path['checkout'],
        env=env,
      )

  def simple_leak_check(self):
    # TODO(machenbach): Add task kill step for windows.
    relative_d8_path = self.m.path.join(
        self.m.path.basename(self.m.chromium.c.build_dir),
        self.m.chromium.c.build_config_fs,
        'd8')
    step_result = self.m.step(
      'Simple Leak Check',
      ['valgrind', '--leak-check=full', '--show-reachable=yes',
       '--num-callers=20', relative_d8_path, '-e', '"print(1+2)"'],
      cwd=self.m.path['checkout'],
      stderr=self.m.raw_io.output(),
      step_test_data=lambda: self.m.raw_io.test_api.stream_output(
          'tons of leaks', stream='stderr')
    )
    step_result.presentation.logs['stderr'] = step_result.stderr.splitlines()
    if not 'no leaks are possible' in (step_result.stderr):
      step_result.presentation.status = self.m.step.FAILURE
      raise self.m.step.StepFailure('Failed leak check')

  def deopt_fuzz(self):
    full_args = [
      '--mode', self.m.chromium.c.build_config_fs,
      '--arch', self.m.chromium.c.gyp_env.GYP_DEFINES['v8_target_arch'],
      '--progress', 'verbose',
      '--buildbot',
    ]

    # Add builder-specific test arguments.
    full_args += self.c.testing.test_args

    self.m.python(
      'Deopt Fuzz',
      self.m.path['checkout'].join('tools', 'run-deopt-fuzzer.py'),
      full_args,
      cwd=self.m.path['checkout'],
    )

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

  def _runtest(self, name, test, flaky_tests=None, failure_factory=None,
               **kwargs):
    env = {}
    full_args = [
      '--progress=verbose',
      '--mode', self.m.chromium.c.build_config_fs,
      '--arch', self.m.chromium.c.gyp_env.GYP_DEFINES['v8_target_arch'],
      '--outdir', self.m.path.split(self.m.chromium.c.build_dir)[-1],
      '--buildbot',
      '--timeout=200',
    ] + list(test['tests'])

    # Add test-specific test arguments.
    full_args += test.get('test_args', [])

    # Add builder-specific test arguments.
    full_args += self.c.testing.test_args

    if self.run_dynamorio:
      drrun = self.m.path['slave_build'].join(
          'dynamorio', 'build', 'bin64', 'drrun')
      full_args += [
        '--command_prefix',
        '%s -reset_every_nth_pending 0 --' % drrun,
      ]

    if self.c.testing.may_shard and self.c.testing.SHARD_COUNT > 1:
      full_args += [
        '--shard-count=%d' % self.c.testing.SHARD_COUNT,
        '--shard-run=%d' % self.c.testing.SHARD_RUN,
      ]

    if flaky_tests:
      full_args += ['--flaky-tests', flaky_tests]

    llvm_symbolizer_path = self.m.path['checkout'].join(
        'third_party', 'llvm-build', 'Release+Asserts', 'bin',
        'llvm-symbolizer')

    # Indicate whether DCHECKs were enabled.
    if self.m.chromium.c.gyp_env.GYP_DEFINES.get('dcheck_always_on') == 1:
      full_args.append('--dcheck-always-on')

    # Arguments and environment for asan builds:
    if self.m.chromium.c.gyp_env.GYP_DEFINES.get('asan') == 1:
      full_args.append('--asan')
      env['ASAN_OPTIONS'] = " ".join([
        'external_symbolizer_path=%s' % llvm_symbolizer_path,
      ])

    # Arguments and environment for tsan builds:
    if self.m.chromium.c.gyp_env.GYP_DEFINES.get('tsan') == 1:
      full_args.append('--tsan')
      env['TSAN_OPTIONS'] = " ".join([
        'external_symbolizer_path=%s' % llvm_symbolizer_path,
        'exit_code=0',
        'report_thread_leaks=0',
        'history_size=7',
        'report_destroy_locked=0',
      ])

    # Arguments and environment for msan builds:
    if self.m.chromium.c.gyp_env.GYP_DEFINES.get('msan') == 1:
      full_args.append('--msan')
      env['MSAN_OPTIONS'] = " ".join([
        'external_symbolizer_path=%s' % llvm_symbolizer_path,
      ])

    full_args += [
      '--rerun-failures-count=%d' % self.rerun_failures_count,
      '--json-test-results',
      self.m.json.output(add_json_log=False),
    ]
    def step_test_data():
      return self.test_api.output_json(
          self._test_data.get('test_failures', False),
          self._test_data.get('wrong_results', False),
          self._test_data.get('flakes', False))

    step_result = self.m.python(
      name,
      self.m.path['checkout'].join('tools', 'run-tests.py'),
      full_args,
      cwd=self.m.path['checkout'],
      env=env,
      # The outcome is controlled by the json test result of the step.
      ok_ret='any',
      step_test_data=step_test_data,
      **kwargs
    )

    # The output is expected to be a list of architecture dicts that
    # each contain a results list. On buildbot, there is only one
    # architecture.
    assert len(step_result.json.output) == 1
    self._update_durations(
        step_result.json.output[0], step_result.presentation)
    failure_log, failures, flake_log, flakes = (
        self._get_failure_logs(step_result.json.output[0], failure_factory))
    self._update_failure_presentation(
        failure_log, failures, step_result.presentation)

    if failure_log and failures:
      # Mark the test step as failure only if there were real failures (i.e.
      # non-flakes) present.
      step_result.presentation.status = self.m.step.FAILURE

    if flake_log and flakes:
      # Emit a separate step to show flakes from the previous step
      # to not close the tree.
      step_result = self.m.python.inline(name + ' (flakes)', '# Empty program')
      step_result.presentation.status = self.m.step.WARNING
      self._update_failure_presentation(
            flake_log, flakes, step_result.presentation)

    return TestResults(failures, flakes, [])

  def runtest(self, test, failure_factory=None, add_flaky_step_override=None,
              suffix='', **kwargs):
    # Get the flaky-step configuration default per test.
    add_flaky_step = test.get('add_flaky_step', False)

    # Overwrite the flaky-step configuration on a per builder basis as some
    # types of builders (e.g. branch, try) don't have any flaky steps.
    if self.c.testing.add_flaky_step is not None:
      add_flaky_step = self.c.testing.add_flaky_step
    if add_flaky_step_override is not None:
      add_flaky_step = add_flaky_step_override
    if add_flaky_step:
      return (
          self._runtest(
              test['name'] + suffix,
              test,
              flaky_tests='skip',
              failure_factory=failure_factory,
              **kwargs
          ) +
          self._runtest(
              test['name'] + ' - flaky' + suffix,
              test,
              flaky_tests='run',
              failure_factory=failure_factory,
              **kwargs
          )
      )
    else:
      return self._runtest(
          test['name'] + suffix,
          test,
          failure_factory=failure_factory,
          **kwargs
      )

  @staticmethod
  def mean(values):
    return float(sum(values)) / len(values)

  @staticmethod
  def variance(values, average):
    return map(lambda x: (x - average) ** 2, values)

  @staticmethod
  def standard_deviation(values, average):
    return math.sqrt(V8Api.mean(V8Api.variance(values, average)))

  def perf_upload(self, results, category):
    """Upload performance results to the performance dashboard.

    Args:
      results: A list of result maps. Each result map has an errors and a
               traces item.
      category: Name of the perf category (e.g. ia32 or N5). The bot field
                of the performance dashboard is used to hold this category.
    """
    # Make sure that bots that run perf tests have a revision property.
    if results:
      assert self.revision_number and self.revision, (
          'Revision must be specified for perf tests as '
          'they upload data to the perf dashboard.')

    points = []
    for result in results:
      for trace in result['traces']:
        # Make 'v8' the root of all standalone v8 performance tests.
        test_path = '/'.join(['v8'] + trace['graphs'])

        # Ignore empty traces.
        # TODO(machenbach): Show some kind of failure on the waterfall on empty
        # traces without skipping to upload.
        if not trace['results']:
          continue

        values = map(float, trace['results'])
        average = V8Api.mean(values)

        p = self.m.perf_dashboard.get_skeleton_point(
            test_path, self.revision_number, str(average))
        p['units'] = trace['units']
        p['bot'] = category or p['bot']
        p['supplemental_columns'] = {'a_default_rev': 'r_v8_git',
                                     'r_v8_git': self.revision}

        # A trace might provide a value for standard deviation if the test
        # driver already calculated it, otherwise calculate it here.
        p['error'] = (trace.get('stddev') or
                      str(V8Api.standard_deviation(values, average)))

        points.append(p)

    # Send all perf data to the perf dashboard in one step.
    if points:
      self.m.perf_dashboard.post(points)


  def _runperf(self, tests, perf_configs, category=None, suffix='',
              upload=True, extra_flags=None, out_dir_no_patch=None):
    """Run v8 performance tests and upload results.

    Args:
      tests: A list of tests from perf_configs to run.
      perf_configs: A mapping from test name to a suite configuration json.
      category: Optionally use bot nesting level as category. Bot names are
                irrelevant if several different bots run in the same category
                like ia32.
      suffix: Optional name suffix to differentiate multiple runs of the same
              step.
      upload: If true, adds a link to the uploaded data on the performance
              dashboard.
      extra_flags: List of flags to be passed to the test executable.
      out_dir_no_patch: A folder pointing to executables without patch on a
                        trybot. Using this parameter will execute the tests
                        in interleaved mode.
    Returns: A tuple with 1) A mapping of test config name->results map.
             Each results map has an errors and a traces item. 2) A mapping
             without patch. Undefined, if out_dir_no_patch wasn't specified.
             3) A boolean indicating if any step has failed.
    """

    results_mapping = collections.defaultdict(dict)
    results_mapping_no_patch = collections.defaultdict(dict)
    def run_single_perf_test(test, name, json_file, download_test=None):
      """Call the v8 perf test runner.

      Performance results are saved in the json test results file as a dict with
      'errors' for accumulated errors and 'traces' for the measurements.
      """
      full_args = [
        '--arch', self.m.chromium.c.gyp_env.GYP_DEFINES['v8_target_arch'],
        '--buildbot',
        '--json-test-results', self.m.json.output(add_json_log=False),
      ]

      if out_dir_no_patch:
        full_args.extend([
          '--outdir-no-patch', out_dir_no_patch,
          '--json-test-results-no-patch',
          self.m.json.output(add_json_log=False),
        ])

      if extra_flags:
        full_args.extend(['--extra-flags', ' '.join(extra_flags)])

      full_args.append(json_file)

      def step_test_data():
        test_data = self.test_api.perf_json(
            self._test_data.get('perf_failures', False))
        if out_dir_no_patch:
          return test_data + self.test_api.perf_improvement_json()
        else:
          return test_data

      try:
        if download_test is not None:
          self.m.python(
            '%s%s - download-data' % (name, suffix),
            self.m.path['checkout'].join('tools', 'run-tests.py'),
            ['--download-data-only', download_test],
            cwd=self.m.path['checkout'],
          )
        self.m.python(
          '%s%s' % (name, suffix),
          self.m.path['checkout'].join('tools', 'run_perf.py'),
          full_args,
          cwd=self.m.path['checkout'],
          step_test_data=step_test_data,
        )
      finally:
        step_result = self.m.step.active_result
        results_mapping[test] = step_result.json.output_all[0]
        errors = results_mapping[test]['errors']
        if out_dir_no_patch:
          results_mapping_no_patch[test] = step_result.json.output_all[1]
          errors += results_mapping_no_patch[test]['errors']
        if errors:
          step_result.presentation.logs['Errors'] = errors
        elif upload:
          # Add a link to the dashboard. This assumes the naming convention
          # step name == suite name. If this convention didn't hold, we'd need
          # to use the path from the json output graphs here.
          self.m.perf_dashboard.add_dashboard_link(
              step_result.presentation,
              'v8/%s' % name,
              self.revision_number,
              bot=category)

    failed = False
    for t in tests:
      assert perf_configs[t]
      assert perf_configs[t]['name']
      assert perf_configs[t]['json']
      try:
        run_single_perf_test(
            t, perf_configs[t]['name'], perf_configs[t]['json'],
            download_test=perf_configs[t].get('download_test'))
      except self.m.step.StepFailure:
        failed = True

    return results_mapping, results_mapping_no_patch, failed


  def runperf(self, tests, perf_configs, category=None, suffix='',
              upload=True, extra_flags=None):
    """Convenience wrapper."""
    results_mapping, _, failed = self._runperf(
      tests,
      perf_configs,
      category=category,
      upload=upload,
      suffix=suffix,
      extra_flags=extra_flags,
    )

    # Collect all perf data of the previous steps.
    if upload:
      self.perf_upload(
          [results_mapping[k] for k in sorted(results_mapping.keys())],
          category)

    if failed:
      raise self.m.step.StepFailure('One or more performance tests failed.')

    return results_mapping

  def runperf_interleaved(
      self, tests, perf_configs, out_dir_no_patch, category=None,
      extra_flags=None):
    """Convenience wrapper."""
    # A failure of a single step is not required to be raised on perf trybots
    # as the overall builds don't get inspected on a waterfall.
    results_mapping, results_mapping_no_patch, _ = self._runperf(
      tests,
      perf_configs,
      category=category,
      upload=False,
      extra_flags=extra_flags,
      out_dir_no_patch=out_dir_no_patch,
    )
    return results_mapping, results_mapping_no_patch

  # TODO(machenbach): Deprecated in favor of method below.
  def merge_perf_results(self, *args, **kwargs):
    """Merge perf results from a list of result files and return the resulting
    json.
    """
    return self.m.python(
      'merge perf results' + kwargs.pop('suffix', ''),
      self.resource('merge_perf_results.py'),
      map(str, args),
      stdout=self.m.json.output(),
      **kwargs
    ).stdout

  def merge_perf_result_maps(self, results_file_map, **kwargs):
    """Merge perf results from a mapping of result files and return the
    resulting json.
    """
    return self.m.python(
      'merge perf results' + kwargs.pop('suffix', ''),
      self.resource('merge_perf_result_maps.py'),
      [self.m.json.input(results_file_map)],
      stdout=self.m.json.output(),
    ).stdout

  def maybe_trigger(self, **additional_properties):
    triggers = self.bot_config.get('triggers')
    if triggers:
      properties = {
        'revision': self.revision,
        'parent_got_revision': self.revision,
        'parent_got_revision_cp': self.revision_cp,
      }
      properties.update(**additional_properties)
      self.m.trigger(*[{
        'builder_name': builder_name,
        'properties': properties,
      } for builder_name in triggers])

  def get_change_range(self):
    url = '%sjson/builders/%s/builds/%s/source_stamp' % (
        self.m.properties['buildbotURL'],
        urllib.quote(self.m.properties['buildername']),
        str(self.m.properties['buildnumber']),
    )
    step_result = self.m.python(
        'Fetch changes',
        self.m.path['build'].join('scripts', 'tools', 'pycurl.py'),
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

    self.m.git(
        'log', '%s~1..%s' % (first_change, last_change),
        name='Show changes',
        cwd=self.m.path['checkout'],
    )

    step_result = self.m.git(
        'log', '%s~1' % first_change, '--format=%H', '-n1',
        name='Get latest previous change',
        cwd=self.m.path['checkout'],
        stdout=self.m.raw_io.output(),
        step_test_data=lambda: self.test_api.example_latest_previous_hash()
    )
    return (
        step_result.stdout.strip(),
        str(last_change),
        len(changes),
    )

  def get_available_range(self, bisect_range):
    assert self.bot_type == 'tester'
    archive_name_pattern = '%s/full-build-%s_%%s.zip' % (
        self.GS_ARCHIVES[self.bot_config['build_gs_archive']],
        self.m.archive.legacy_platform_name(),
    )
    # TODO(machenbach): Maybe parallelize this in a wrapper script.
    args = ['ls']
    available_range = []
    # Check all builds except the last as we already know it is "bad".
    for r in bisect_range[:-1]:
      step_result = self.m.gsutil(
          args + [archive_name_pattern % r],
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

    step_result = self.m.python.inline(text, '# Empty program')
    for culprit in culprit_range:
      step_result.presentation.links[culprit[:8]] = COMMIT_TEMPLATE % culprit
