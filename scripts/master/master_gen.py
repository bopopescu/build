# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import os

from buildbot.changes.filter import ChangeFilter
from buildbot.schedulers.basic import SingleBranchScheduler
from buildbot.schedulers.timed import Nightly
from buildbot.status.mail import MailNotifier
from buildbot import util

from config_bootstrap import Main

from common import chromium_utils

from main import gitiles_poller
from main import main_utils
from main import repo_poller
from main import subordinates_list
from main.factory import annotator_factory


def PopulateBuildmainConfig(BuildmainConfig, builders_path,
                              active_main_cls):
  """Read builders_path and populate a build main config dict."""
  builders = chromium_utils.ReadBuildersFile(builders_path)
  _Populate(BuildmainConfig, builders, active_main_cls)


def _Populate(BuildmainConfig, builders, active_main_cls):
  m_annotator = annotator_factory.AnnotatorFactory(active_main_cls)

  c = BuildmainConfig
  c['logCompressionLimit'] = False
  c['projectName'] = active_main_cls.project_name
  c['projectURL'] = Main.project_url
  c['buildbotURL'] = active_main_cls.buildbot_url

  # This sets c['db_url'] to the database connect string in found in
  # the .dbconfig in the main directory, if it exists. If this is
  # a production host, it must exist.
  chromium_utils.DatabaseSetup(
      c,
      require_dbconfig=active_main_cls.is_production_host)

  c['builders'] = _ComputeBuilders(builders, m_annotator)

  c['schedulers'] = _ComputeSchedulers(builders)

  c['change_source'], tag_comparator = _ComputeChangeSourceAndTagComparator(
      builders)

  # The 'subordinates' list defines the set of allowable buildsubordinates. List all the
  # subordinates registered to a builder. Remove dupes.
  c['subordinates'] = main_utils.AutoSetupSubordinates(
      c['builders'],
      Main.GetBotPassword())

  # This does some sanity checks on the configuration.
  subordinates = subordinates_list.BaseSubordinatesList(
      chromium_utils.GetSubordinatesFromBuilders(builders),
      builders['main_classname'])
  main_utils.VerifySetup(c, subordinates)

  default_public_html = os.path.join(chromium_utils.BUILD_DIR,
                                     'mains', 'main.chromium',
                                     'public_html')
  public_html = builders.get('public_html', default_public_html)

  # Adds common status and tools to this main.
  # TODO: Look at the logic in this routine to see if any of the logic
  # in this routine can be moved there to simplify things.
  main_utils.AutoSetupMain(c, active_main_cls,
      public_html=public_html,
      templates=builders['templates'],
      tagComparator=tag_comparator,
      enable_http_status_push=active_main_cls.is_production_host)

  # TODO: AutoSetupMain's settings for the following are too low to be
  # useful for most projects. We should fix that.
  c['buildHorizon'] = 3000
  c['logHorizon'] = 3000
  # Must be at least 2x the number of subordinates.
  c['eventHorizon'] = 200


def _ComputeBuilders(builders, m_annotator):
  actual_builders = []

  def cmp_fn(a, b):
    a_cat = builders['builders'][a].get('category')
    b_cat = builders['builders'][b].get('category')
    if a_cat != b_cat:
      return 1 if a_cat > b_cat else -1
    if a != b:
      return 1 if a > b else -1
    return 0

  for builder_name in sorted(builders['builders'], cmp=cmp_fn):
    builder_data = builders['builders'][builder_name]
    has_schedulers = bool(
        builder_data.get('scheduler', builder_data.get('schedulers')))

    # We will automatically merge all build requests for any
    # builder that can be scheduled; this is normally the behavior
    # we want for repo-triggered builders and cron-triggered builders.
    # You can override this behavior by setting the mergeRequests field though.
    merge_requests = builder_data.get('mergeRequests', has_schedulers)

    subordinatebuilddir = builder_data.get('subordinatebuilddir',
                                     util.safeTranslate(builder_name))
    factory = m_annotator.BaseFactory(
        recipe=builder_data['recipe'],
        max_time=builder_data.get('builder_timeout_s'),
        factory_properties=builder_data.get('properties')
    )
    actual_builders.append({
        'auto_reboot': builder_data.get('auto_reboot', True),
        'mergeRequests': merge_requests,
        'name': builder_name,
        'factory': factory,
        'subordinatebuilddir': subordinatebuilddir,
        'subordinatenames': chromium_utils.GetSubordinateNamesForBuilder(builders,
                                                             builder_name),
        'category': builder_data.get('category'),
        'trybot': builder_data.get('trybot'),
    })

  return actual_builders


def _ComputeSchedulers(builders):
  scheduler_to_builders = {}
  for builder_name, builder_data in builders['builders'].items():
    scheduler_names = builder_data.get('schedulers', [])
    if 'scheduler' in builder_data:
      scheduler_names.append(builder_data['scheduler'])
    for scheduler_name in scheduler_names:
      if scheduler_name:
        if scheduler_name not in builders['schedulers']:
          raise ValueError('unknown scheduler "%s"' % scheduler_name)
        scheduler_to_builders.setdefault(
            scheduler_name, []).append(builder_name)

  schedulers = []
  for scheduler_name, scheduler_values in builders['schedulers'].items():
    scheduler_type = scheduler_values['type']
    builder_names = scheduler_to_builders[scheduler_name]

    if scheduler_type == 'git_poller':
      # git_poller pollers group changes, so we match on our specific repository
      # to ensure that we only pick up changes from our poller.
      schedulers.append(SingleBranchScheduler(
          name=scheduler_name,
          change_filter=ChangeFilter(
              repository=scheduler_values['git_repo_url'],
              branch=scheduler_values.get('branch', 'main'),
          ),
          treeStableTimer=scheduler_values.get('treeStableTimer', 60),
          builderNames=builder_names))

    elif scheduler_type == 'repo_poller':
      # repo_poller pollers punt changes that use the scheduler name as their
      # category (see _ComputeChangeSourceAndTagComparator). Matching on this
      # ensures that we only match changes from our poller.
      schedulers.append(SingleBranchScheduler(
          name=scheduler_name,
          change_filter=ChangeFilter(
              category=str(scheduler_name),
          ),
          treeStableTimer=scheduler_values.get('treeStableTimer', 60),
          builderNames=builder_names))

    elif scheduler_type == 'cron':
      schedulers.append(Nightly(
          name=scheduler_name,
          branch='main',
          minute=scheduler_values['minute'],
          hour=scheduler_values['hour'],
          builderNames=builder_names))

    else:
      raise ValueError('unsupported scheduler type "%s"' % scheduler_type)

  return schedulers


def _ComputeChangeSourceAndTagComparator(builders):
  change_source = []
  tag_comparator = None

  git_urls_to_branches = {}
  for scheduler_config in builders['schedulers'].values():
    if scheduler_config['type'] != 'git_poller':
      continue

    url = scheduler_config['git_repo_url']
    branch = scheduler_config.get('branch', 'main')
    git_urls_to_branches.setdefault(url, set()).add(branch)

  for url, branches in git_urls_to_branches.iteritems():
    change_source.append(
        gitiles_poller.GitilesPoller(url, branches=list(branches)))

  for scheduler_name, scheduler_config in builders['schedulers'].iteritems():
    if scheduler_config['type'] != 'repo_poller':
      continue

    rev_link_template = scheduler_config.get('rev_link_template')
    branch = scheduler_config.get('branch')
    branches = [branch] if branch is not None else None
    change_source.append(repo_poller.RepoPoller(
        repo_url=scheduler_config['repo_url'],
        manifest='manifest',
        category=str(scheduler_name),
        repo_branches=branches,
        pollInterval=300,
        revlinktmpl=rev_link_template))

  # We have to set the tag_comparator to something, but if we have multiple
  # repos, the tag_comparator will not work properly (it's meaningless).
  # It's not clear if there's a good answer to this.
  if change_source:
    tag_comparator = change_source[0].comparator

  return change_source, tag_comparator
