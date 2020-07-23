# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Skia-specific utilities for setting up build mains."""


from buildbot.changes import filter as change_filter
from buildbot.scheduler import AnyBranchScheduler
from buildbot.scheduler import Scheduler
from buildbot.scheduler import Triggerable
from buildbot.schedulers import timed
from buildbot.status.status_push import HttpStatusPush
from common import chromium_utils
from common.skia import builder_name_schema
from common.skia import global_constants
from main import main_utils
from main import subordinates_list
from main import status_logger
from main.builders_pools import BuildersPools
from main.factory import annotator_factory
from main.gitiles_poller import GitilesPoller
from main.skia import status_json
from main.skia import skia_notifier
from twisted.python import log

import collections
import config
import re


DEFAULT_AUTO_REBOOT = False
DEFAULT_DO_TRYBOT = True
DEFAULT_RECIPE = 'skia/skia'
DEFAULT_TRYBOT_ONLY = False
BUILDBUCKET_SCHEDULER_NAME = 'buildbucket'
MASTER_ONLY_SCHEDULER_NAME = 'skia_main_only'
PERIODIC_15MINS_SCHEDULER_NAME = 'skia_periodic_15mins'
NIGHTLY_SCHEDULER_NAME = 'skia_nightly'
WEEKLY_SCHEDULER_NAME = 'skia_weekly'
FAKE_TRY_SCHEDULER_NAME = 'skia_trybots'
MASTER_BRANCH = 'main'
POLLING_BRANCH = re.compile('refs/heads/(?!infra/config).+')
SLAVE_WORKDIR = 'workdir'

SCHEDULERS = [
  MASTER_ONLY_SCHEDULER_NAME,
  PERIODIC_15MINS_SCHEDULER_NAME,
  NIGHTLY_SCHEDULER_NAME,
  WEEKLY_SCHEDULER_NAME,
  BUILDBUCKET_SCHEDULER_NAME,
  FAKE_TRY_SCHEDULER_NAME,
]

KEYWORD_NO_MERGE_BUILDS = 'NO_MERGE_BUILDS'


def CanMergeBuildRequests(req1, req2):
  """Determine whether or not two BuildRequests can be merged.

  Rewrite of buildbot.sourcestamp.SourceStamp.canBeMergedWith(), which
  verifies that:
  1. req1.source.repository == req2.source.repository
  2. req1.source.project == req2.source.project
  3. req1.source.branch == req2.source.branch
  4. req1.patch == None and req2.patch = None
  5. (req1.source.changes and req2.source.changes) or \
     (not req1.source.changes and not req2.source.changes and \
      req1.source.revision == req2.source.revision)

  Of the above, we want 1, 2, 3, and 5.
  Instead of 4, we want to make sure that neither request is a Trybot request.
  """
  # Verify that the repositories are the same (#1 above).
  if req1.source.repository != req2.source.repository:
    return False

  # Verify that the projects are the same (#2 above).
  if req1.source.project != req2.source.project:
    return False

  # Verify that the branches are the same (#3 above).
  if req1.source.branch != req2.source.branch:
    return False

  # If either is a try request, don't merge (#4 above).
  if (builder_name_schema.IsTrybot(req1.buildername) or
      builder_name_schema.IsTrybot(req2.buildername)):
    return False

  # Verify that either: both requests are associated with changes OR neither
  # request is associated with a change but the revisions match (#5 above).
  if req1.source.changes and not req2.source.changes:
    return False
  if not req1.source.changes and req2.source.changes:
    return False
  if req1.source.changes and req2.source.changes:
    for ch in (req1.source.changes + req2.source.changes):
      if KEYWORD_NO_MERGE_BUILDS in ch.comments:
        return False
  else:
    if req1.source.revision != req2.source.revision:
      return False

  return True


def SetupBuildersAndSchedulers(c, builders, subordinates, ActiveMain):
  """Set up builders and schedulers for the build main."""
  # List of dicts for every builder.
  builder_dicts = []

  # Builder names by scheduler.
  builders_by_scheduler = {s: [] for s in SCHEDULERS}
  # Maps a triggering builder to its triggered builders.
  triggered_builders = collections.defaultdict(list)

  def process_builder(builder, is_trybot=False):
    """Create a dict for the given builder and place its name in the
    appropriate scheduler list.
    """
    builder_name = builder['name']
    if is_trybot:
      builder_name = builder_name_schema.TrybotName(builder_name)

    # Categorize the builder based on its role.
    try:
      category = builder_name_schema.DictForBuilderName(builder_name)['role']
      subcategory = builder_name.split(builder_name_schema.BUILDER_NAME_SEP)[1]
      category = '|'.join((category, subcategory))
    except ValueError:
      # Assume that all builders whose names don't play by our rules are named
      # upstream and are therefore canaries.
      category = builder_name_schema.BUILDER_ROLE_CANARY

    properties = builder.get('properties', {})
    cc = builder.get('cc')
    if cc:
      if isinstance(cc, basestring):
        cc = [cc]
      properties['owners'] = cc
    builder_dict = {
      'name': builder_name,
      'auto_reboot': builder.get('auto_reboot', DEFAULT_AUTO_REBOOT),
      'subordinatenames': subordinates.GetSubordinatesName(builder=builder['name']),
      'category': category,
      'recipe': builder.get('recipe', DEFAULT_RECIPE),
      'properties': properties,
      'mergeRequests': builder.get('can_merge_requests', CanMergeBuildRequests),
      'subordinatebuilddir': SLAVE_WORKDIR,
    }
    builder_dicts.append(builder_dict)

    parent_builder = builder.get('triggered_by')
    if parent_builder is not None:
      assert builder.get('scheduler') is None
      if is_trybot:
        parent_builder = builder_name_schema.TrybotName(parent_builder)
      triggered_builders[parent_builder].append(builder_name)
    elif is_trybot:
      builders_by_scheduler[FAKE_TRY_SCHEDULER_NAME].append(builder_name)
    else:
      scheduler = builder.get('scheduler', BUILDBUCKET_SCHEDULER_NAME)
      # Setting the scheduler to BUILDBUCKET_SCHEDULER_NAME indicates that
      # BuildBucket is the only way to schedule builds for this bot; just
      # pretend to add a scheduler in those cases.
      builders_by_scheduler[scheduler].append(builder_name)

  # Create builders and trybots.
  for builder in builders:
    if builder.get('trybot_only', DEFAULT_TRYBOT_ONLY):
      # trybot_only=True should only be used in combination with do_trybot=True
      # Also, the buildername then needs to already have the '-Trybot' suffix.
      assert builder.get('do_trybot', DEFAULT_DO_TRYBOT)
      assert builder['name'] == builder_name_schema.TrybotName(builder['name'])
    else:
      process_builder(builder)
    if builder.get('do_trybot', DEFAULT_DO_TRYBOT):
      process_builder(builder, is_trybot=True)

  # Verify that all parent builders exist.
  buildbucket_builders = set(
      builders_by_scheduler[BUILDBUCKET_SCHEDULER_NAME]
  )
  trybots = set(builders_by_scheduler[FAKE_TRY_SCHEDULER_NAME])
  trigger_parents = set(triggered_builders.keys())
  nonexistent_parents = trigger_parents - buildbucket_builders - trybots
  if nonexistent_parents:
    raise Exception('Could not find parent builders: %s' %
                    ', '.join(nonexistent_parents))

  # Create the schedulers.
  skia_main_only_change_filter = change_filter.ChangeFilter(
      project='skia', repository=ActiveMain.repo_url, branch=MASTER_BRANCH)

  c['schedulers'] = []

  s = Scheduler(
      name=MASTER_ONLY_SCHEDULER_NAME,
      treeStableTimer=60,
      change_filter=skia_main_only_change_filter,
      builderNames=builders_by_scheduler[MASTER_ONLY_SCHEDULER_NAME])
  c['schedulers'].append(s)

  s = timed.Nightly(
      name=PERIODIC_15MINS_SCHEDULER_NAME,
      branch=MASTER_BRANCH,
      builderNames=builders_by_scheduler[PERIODIC_15MINS_SCHEDULER_NAME],
      minute=[i*15 for i in xrange(60/15)],
      hour='*',
      dayOfMonth='*',
      month='*',
      dayOfWeek='*')
  c['schedulers'].append(s)

  s = timed.Nightly(
      name=NIGHTLY_SCHEDULER_NAME,
      branch=MASTER_BRANCH,
      builderNames=builders_by_scheduler[NIGHTLY_SCHEDULER_NAME],
      minute=0,
      hour=22,
      dayOfMonth='*',
      month='*',
      dayOfWeek='*')
  c['schedulers'].append(s)

  s = timed.Nightly(
      name=WEEKLY_SCHEDULER_NAME,
      branch=MASTER_BRANCH,
      builderNames=builders_by_scheduler[WEEKLY_SCHEDULER_NAME],
      minute=0,
      hour=0,
      dayOfMonth='*',
      month='*',
      dayOfWeek=6) # Sunday (Monday = 0).
  c['schedulers'].append(s)

  # Don't add triggerable schedulers for triggered_builders; triggers are now
  # handled on the subordinate-side through buildbucket.

  # Create the BuildFactorys.
  annotator = annotator_factory.AnnotatorFactory(ActiveMain)

  for builder_dict in builder_dicts:
    factory = annotator.BaseFactory(
        builder_dict['recipe'],
        timeout=2400)
    factory.properties.update(builder_dict['properties'], 'BuildFactory')
    builder_dict['factory'] = factory

  # Finished!
  c['builders'] = builder_dicts


def SetupMain(ActiveMain):
  # Buildmain config dict.
  c = {}

  config.DatabaseSetup(c, require_dbconfig=ActiveMain.is_production_host)

  ####### CHANGESOURCES

  # Polls config.Main.trunk_url for changes
  poller = GitilesPoller(
      repo_url=ActiveMain.repo_url,
      branches=[POLLING_BRANCH],
      pollInterval=10,
      revlinktmpl='https://skia.googlesource.com/skia/+/%s')

  c['change_source'] = [poller]

  ####### SLAVES

  # Load the subordinate list. We need some information from it in order to
  # produce the builders.
  subordinates = subordinates_list.SubordinatesList('subordinates.cfg', ActiveMain.project_name)

  ####### BUILDERS

  # Load the builders list.
  builders = chromium_utils.ParsePythonCfg('builders.cfg')['builders']

  # Configure the Builders and Schedulers.
  SetupBuildersAndSchedulers(c=c, builders=builders, subordinates=subordinates,
                             ActiveMain=ActiveMain)

  ####### BUILDSLAVES

  # The 'subordinates' list defines the set of allowable buildsubordinates. List all the
  # subordinates registered to a builder. Remove dupes.
  c['subordinates'] = main_utils.AutoSetupSubordinates(c['builders'],
                                             config.Main.GetBotPassword())
  main_utils.VerifySetup(c, subordinates)

  ####### STATUS TARGETS

  c['buildbotURL'] = ActiveMain.buildbot_url

  # Adds common status and tools to this main.
  main_utils.AutoSetupMain(c, ActiveMain,
      public_html='../../../build/mains/main.client.skia/public_html',
      templates=['../../../build/mains/main.client.skia/templates',
                 '../../../build/mains/main.chromium/templates'],
      tagComparator=poller.comparator,
      enable_http_status_push=ActiveMain.is_production_host,
      order_console_by_time=True,
      console_repo_filter=ActiveMain.repo_url,
      console_builder_filter=lambda b: not builder_name_schema.IsTrybot(b))

  with status_json.JsonStatusHelper() as json_helper:
    json_helper.putChild('trybots', status_json.TryBuildersJsonResource)

  if (ActiveMain.is_production_host and
      ActiveMain.project_name != 'SkiaInternal'):
    # Build result emails.
    c['status'].append(status_logger.StatusEventLogger())
    c['status'].append(skia_notifier.SkiaMailNotifier(
        fromaddr=ActiveMain.from_address,
        mode='change',
        relayhost=config.Main.smtp,
        lookup=main_utils.UsersAreEmails()))

    # Try job result emails.
    c['status'].append(skia_notifier.SkiaTryMailNotifier(
        fromaddr=ActiveMain.from_address,
        subject="try %(result)s for %(reason)s @ r%(revision)s",
        mode='all',
        relayhost=config.Main.smtp,
        lookup=main_utils.UsersAreEmails()))

    # Push status updates to GrandCentral.
    c['status'].append(HttpStatusPush(
        serverUrl='https://grandcentral.skia.org/buildbot'))

  c['mergeRequests'] = CanMergeBuildRequests

  ###### LOGS

  # Skia bots have been known to have run away builds continously dumping to
  # stdout and creating ~100GB logs. See crbug.com/589654 for context.
  c['logMaxSize'] = 1024 * 1024 * 100 # 100MB
  c['logMaxTailSize'] = 1024 * 32 # 32KB

  return c
