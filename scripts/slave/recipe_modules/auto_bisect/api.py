# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""API for the bisect recipe module.

This API is meant to enable the bisect recipe to bisect any chromium-supported
platform for any test that can be run via buildbot, perf or otherwise.
"""

import os

from recipe_engine import recipe_api
from . import bisector
from . import depot_config
from . import revision_state
from . import local_bisect

BISECT_CONFIG_FILE = 'tools/auto_bisect/bisect.cfg'


class AutoBisectApi(recipe_api.RecipeApi):
  """A module for bisect specific functions."""

  # Number of seconds to wait between polls for test results.
  POLLING_INTERVAL = 60
  # GS bucket to use for communicating results and job state between bisector
  # and tester bots.
  BUCKET = 'chrome-perf'
  # Directory within the above bucket to store results.
  RESULTS_GS_DIR = 'bisect-results'
  GS_RESULTS_URL = 'gs://%s/%s/' % (BUCKET, RESULTS_GS_DIR)
  # Email to send on try jobs (for build requests) since git try will not
  # necessarily rely on a local checkout for that information.
  BOT_EMAIL = 'chrome_bot@chromium.org'

  def __init__(self, *args, **kwargs):
    super(AutoBisectApi, self).__init__(*args, **kwargs)
    self.override_poll_interval = None
    self.bot_db = None
    # Repo for triggering build jobs.
    self.svn_repo_url = 'svn://svn.chromium.org/chrome-try/try-perf'    
    # The variable below are set and used for the internal bisects.
    self.buildurl_gs_prefix = None
    self.internal_bisect = False
    self.builder_bot = None
    self.full_deploy_script = None

  def perform_bisect(self):
    return local_bisect.perform_bisect(self)

  def create_bisector(self, bisect_config_dict, dummy_mode=False):
    """Passes the api and the config dictionary to the Bisector constructor.

    For details about the keys in the bisect config dictionary go to:
    http://chromium.org/developers/speed-infra/perf-try-bots-bisect-bots/config

    Args:
      bisect_config_dict (dict): Contains the configuration for the bisect job.
      dummy_mode (bool): In dummy mode we prevent the bisector for expanding
        the revision range at construction, to avoid the need for lots of step
        data when performing certain tests (such as results output).

    Returns:
      An instance of bisector.Bisector.
    """
    self.override_poll_interval = bisect_config_dict.get('poll_sleep')
    return bisector.Bisector(self, bisect_config_dict,
                             revision_state.RevisionState,
                             init_revisions=not dummy_mode)

  def set_platform_gs_prefix(self, gs_url):
    """Sets GS path for the platform."""
    self.buildurl_gs_prefix = gs_url  # pragma: no cover

  def set_builder_bot(self, builder_bot):
    """Sets builder name for building binaries."""
    self.builder_bot = builder_bot  # pragma: no cover

  def set_internal(self):
    """Sets bisector as internal only to process android-chrome."""
    self.internal_bisect = True  # pragma: no cover

  def set_additional_depot_info(self, depot_info):
    """Adds additional depot info to the global depot variables."""
    depot_config.add_addition_depot_into(depot_info)  # pragma: no cover

  def set_deploy_script(self, path):  # pragma: no cover
    """Sets apk deployment script path for android-chrome."""
    self.full_deploy_script = path

  def set_svn_repo(self, svn_repo_url):  # pragma: no cover
    """Sets SVN repo url for triggering build jobs."""
    self.svn_repo_url = svn_repo_url

  def gsutil_file_exists(self, path):
    """Returns True if a file exists at the given GS path."""
    try:
      self.m.gsutil(['ls', path])
    except self.m.step.StepFailure:  # pragma: no cover
      return False
    return True

  def query_revision_info(self, revision):
    """Gathers information on a particular revision.

    Args:
      revision (str): A git commit hash.

    Returns:
      A dict with the keys "author", "email", "date", "subject" and "body",
      as output by fetch_revision_info.py.
    """
    result = self.m.python(
        'Reading culprit cl information.',
        self.resource('fetch_revision_info.py'),
        [revision.commit_hash, revision.depot_name],
        stdout=self.m.json.output())
    return result.stdout

  def run_bisect_script(self, **kwargs):
    """Executes src/tools/run-perf-bisect-regression.py to perform bisection."""
    self.m.python(
        'Preparing for Bisection',
        script=self.m.path['checkout'].join(
            'tools', 'prepare-bisect-perf-regression.py'),
        args=['-w', self.m.path['subordinate_build']])
    args = []

    kwargs['allow_subannotations'] = True

    if kwargs.get('extra_src'):
      args = args + ['--extra_src', kwargs.pop('extra_src')]
    if kwargs.get('path_to_config'):
      args = args + ['--path_to_config', kwargs.pop('path_to_config')]
    if self.m.chromium.c.TARGET_PLATFORM != 'android':
      # TODO(phajdan.jr): update for swarming, http://crbug.com/585401 .
      args += ['--path_to_goma', self.m.path['build'].join('goma')]
    args += [
        '--build-properties',
        self.m.json.dumps(dict(self.m.properties.legacy())),
    ]
    self.m.chromium.runtest(
        self.m.path['checkout'].join('tools', 'run-bisect-perf-regression.py'),
        ['-w', self.m.path['subordinate_build']] + args,
        name='Running Bisection',
        xvfb=True, **kwargs)

  def run_local_test_run(self, test_config_params,
                         skip_download=False):  # pragma: no cover
    """Starts a test run on the same machine.

    This is for the merged director/tester flow.
    """
    if self.m.platform.is_win:
      self.m.chromium.taskkill()

    if skip_download:
      update_step = None
    else:
      update_step = self._SyncRevisionToTest(test_config_params)
    self.start_test_run_for_bisect(update_step, self.bot_db,
                                   test_config_params, run_locally=True,
                                   skip_download=skip_download)

  def _SyncRevisionToTest(self, test_config_params):  # pragma: no cover
    if not self.internal_bisect:
      return self.m.bot_update.ensure_checkout(
          root_solution_revision=test_config_params['revision'])
    else:
      return self._SyncRevisionsForAndroidChrome(
          test_config_params['revision_ladder'])

  def _SyncRevisionsForAndroidChrome(self, revision_ladder):  # pragma: no cover
    """Syncs android-chrome and chromium repos to particular revision."""
    revisions = []
    for d, r in revision_ladder.iteritems():
      revisions.append('%s@%s' % (depot_config.DEPOT_DEPS_NAME[d]['src'], r))
    params = ['sync', '--verbose', '--nohooks', '--force',
              '--delete_unversioned_trees']
    for revision in revisions:
      params.extend(['--revision', revision])
    self.m.gclient('sync %s' % '-'.join(revisions), params)
    return None

  def start_test_run_for_bisect(self, update_step, bot_db,
                                test_config_params, run_locally=False,
                                skip_download=False):
    mainname = self.m.properties.get('mainname')
    buildername = self.m.properties.get('buildername')
    bot_config = bot_db.get_bot_config(mainname, buildername)
    build_archive_url = test_config_params['parent_build_archive_url']
    if not run_locally:
      self.m.bisect_tester.upload_job_url()
    if not skip_download:
      if self.m.chromium.c.TARGET_PLATFORM == 'android':
        # The best way to ensure the old build directory is not used is to
        # remove it.
        build_dir = self.m.chromium.c.build_dir.join(
            self.m.chromium.c.build_config_fs)
        self.m.file.rmtree('build directory', build_dir)

        # The way android builders on tryserver.chromium.perf are archived is
        # different from builders on chromium.perf. In order to support both
        # forms of archives, we added this temporary hack until builders are
        # fixed. See http://crbug.com/535218.
        zip_dir = self.m.path.join(self.m.path['checkout'], 'full-build-linux')
        if self.m.path.exists(zip_dir):  # pragma: no cover
          self.m.file.rmtree('full-build-linux directory', zip_dir)

        gs_bucket = 'gs://%s/' % bot_config['bucket']
        archive_path = build_archive_url[len(gs_bucket):]
        self.m.chromium_android.download_build(
            bucket=bot_config['bucket'],
            path=archive_path)

        # The way android builders on tryserver.chromium.perf are archived is
        # different from builders on chromium.perf. In order to support both
        # forms of archives, we added this temporary hack until builders are
        # fixed. See http://crbug.com/535218.
        if self.m.path.exists(zip_dir):  # pragma: no cover
          self.m.python.inline(
              'moving full-build-linux to out/Release',
              """
              import shutil
              import sys
              shutil.move(sys.argv[1], sys.argv[2])
              """,
              args=[zip_dir, build_dir])
      else:
        self.m.chromium_tests.download_and_unzip_build(
            mainname, buildername, update_step, bot_db,
            build_archive_url=build_archive_url,
            build_revision=test_config_params['parent_got_revision'],
            override_bot_type='tester')

    tests = [self.m.chromium_tests.steps.BisectTest(test_config_params)]

    if not tests:  # pragma: no cover
      return
    self.m.chromium_tests.configure_swarming(  # pragma: no cover
        'chromium', precommit=False, mainname=mainname)
    test_runner = self.m.chromium_tests.create_test_runner(self.m, tests)

    bot_config_object = self.m.chromium_tests.create_bot_config_object(
        mainname, buildername)
    with self.m.chromium_tests.wrap_chromium_tests(bot_config_object, tests):
      if self.m.chromium.c.TARGET_PLATFORM == 'android' and not skip_download:
        deploy_apks = []
        deploy_args = []
        if self.internal_bisect:  # pragma: no cover
          deploy_args = list(bot_config['deploy_args'])
          deploy_apks = bot_config.get('deploy_apks')
          if deploy_apks:
            deploy_args.extend([
              '--apks',
              ','.join(str(self.m.chromium_android.apk_path(apk))
                       for apk in deploy_apks)])
        else:
          if bot_config.get('webview'):
            deploy_apks = ['SystemWebView.apk', 'SystemWebViewShell.apk']
          else:
            deploy_apks = ['ChromePublic.apk']
        self.deploy_apk_on_device(
            self.full_deploy_script, deploy_apks, deploy_args)
      test_runner()

  def deploy_apk_on_device(self, deploy_script, deploy_apks, deploy_args):
    """Installs apk on the android device."""
    if deploy_script:  # pragma: no cover
      self.full_deploy_on_device(deploy_script, deploy_args)
    else:
      for apk in deploy_apks:
        self.m.chromium_android.adb_install_apk(apk)

  def full_deploy_on_device(self, deploy_script, args=None):  # pragma: no cover
    """Install android-chrome apk on device."""
    full_deploy_flags = [
        '-v',
        '--blacklist-file', self.m.chromium_android.blacklist_file,
        '--perfbot',
        '--release',        
    ]
    if args:
      full_deploy_flags += args
    self.m.python(
        'Deploy on Device',
        deploy_script,
        full_deploy_flags,
        infra_step=True,
        env=self.m.chromium.get_env())
  
  def start_try_job(self, api, update_step=None, bot_db=None, **kwargs):
    """Starts a recipe bisect job, perf test run, or legacy bisect run.

    This function is an entry point for:
      1. A legacy bisect job run (in this case, there will be a patch
         with a bisect config file).
      2. A recipe bisect job run (in this case, there will be a property
         called bisect_config which contains the config parameters).
      3. A single test run for a recipe bisect job (there will be a
         bisect_config property but it won't contain good/bad revisions).
      4. A perf try job run.

    Args:
      api: The recipe api object.
      update_step: Extra update_step to, used for some job types.
      bot_db: A BotConfigAndTestDB object, used for some job types.
      kwargs: Args to use only for legacy bisect.
    """
    if bot_db is None:  # pragma: no cover
      self.bot_db = api.chromium_tests.create_bot_db_from_main_dict(
          '', None, None)
    else:
      self.bot_db = bot_db
    affected_files = self.m.tryserver.get_files_affected_by_patch()
    # Skip device setup for internal bisect as it is taken care in
    # internal recipes.
    if api.chromium.c.TARGET_PLATFORM == 'android' and not self.internal_bisect:
      api.chromium_android.common_tests_setup_steps(
          perf_setup=True, remove_system_webview=True)
      api.chromium.runhooks()
    try:
      # Run legacy bisect script if the patch contains bisect.cfg.
      if BISECT_CONFIG_FILE in affected_files:
        self.run_bisect_script(**kwargs)
      elif api.properties.get('bisect_config'):
        # We can distinguish between a config for a full bisect vs a single
        # test by checking for the presence of the good_revision key.
        if api.properties.get('bisect_config').get('good_revision'):
          local_bisect.perform_bisect(self)  # pragma: no cover
        else:
          self.start_test_run_for_bisect(update_step, self.bot_db,
                                         api.properties)
      else:
        self.m.perf_try.start_perf_try_job(
            affected_files, update_step, self.bot_db)
    finally:
      if api.chromium.c.TARGET_PLATFORM == 'android':
        api.chromium_android.common_tests_final_steps()
