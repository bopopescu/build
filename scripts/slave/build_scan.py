#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Scans a list of mains and saves information in a build_db."""

from contextlib import closing
import json
import logging
import optparse
import os
import sys
import urllib
import urllib2

from common import chromium_utils
from subordinate import build_scan_db

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..')

# Buildbot status enum.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)


def get_root_json(main_url):
  """Pull down root JSON which contains builder and build info."""
  logging.info('opening %s' % (main_url + '/json'))
  with closing(urllib2.urlopen(main_url + '/json')) as f:
    return json.load(f)


def find_new_builds(main_url, root_json, build_db):
  """Given a dict of previously-seen builds, find new builds on each builder.

  Note that we use the 'cachedBuilds' here since it should be faster, and this
  script is meant to be run frequently enough that it shouldn't skip any builds.

  'Frequently enough' means 1 minute in the case of Buildbot or cron, so the
  only way for the scan to be overwhelmed is if > cachedBuilds builds
  complete within 1 minute. As cachedBuilds is scaled per number of subordinates per
  builder, the only way for this to really happen is if a build consistently
  takes < 1 minute to complete.
  """
  new_builds = {}
  build_db.mains[main_url] = build_db.mains.get(main_url, {})

  last_finished_build = {}
  for builder, builds in build_db.mains[main_url].iteritems():
    finished = [int(y[0]) for y in builds.iteritems()
                if y[1].finished]
    if finished:
      last_finished_build[builder] = max(finished)

  for buildername, builder in root_json['builders'].iteritems():
    # cachedBuilds are the builds in the cache, while currentBuilds are the
    # currently running builds. Thus cachedBuilds can be unfinished or finished,
    # while currentBuilds are always unfinished.
    candidate_builds = set(builder['cachedBuilds'] + builder['currentBuilds'])
    if buildername in last_finished_build:
      new_builds[buildername] = [
          buildnum for buildnum in candidate_builds
          if buildnum > last_finished_build[buildername]]
    else:
      if buildername in build_db.mains[main_url]:
        # We've seen this builder before, but haven't seen a finished build.
        # Scan finished builds as well as unfinished.
        new_builds[buildername] = candidate_builds
      else:
        # We've never seen this builder before, only scan unfinished builds.

        # We're explicitly only dealing with current builds since we haven't
        # seen this builder before. Thus, the next time a scan is run,
        # only unfinished builds will be in the build_db. This immediately drops
        # us into the section above (builder is in the db, but no finished
        # builds yet.) In this state all the finished builds will be loaded in,
        # firing off an email storm any time the build_db changes or a new
        # builder is added. We set the last finished build here to prevent that.
        finished = set(builder['cachedBuilds']) - set(builder['currentBuilds'])
        if finished:
          build_db.mains[main_url].setdefault(buildername, {})[
              max(finished)] = build_scan_db.gen_build(finished=True)

        new_builds[buildername] = builder['currentBuilds']

  return new_builds


def find_new_builds_per_main(mains, build_db):
  """Given a list of mains, find new builds and collect them under a dict."""
  builds = {}
  main_jsons = {}
  for main in mains:
    root_json = get_root_json(main)
    main_jsons[main] = root_json
    builds[main] = find_new_builds(main, root_json, build_db)
  return builds, main_jsons


def get_build_json(url_tuple):
  """Downloads the json of a specific build."""
  url, main, builder, buildnum = url_tuple
  logging.debug('opening %s...' % url)
  with closing(urllib2.urlopen(url)) as f:
    return json.load(f), main, builder, buildnum


def get_build_jsons(main_builds, processes):
  """Get all new builds on specified mains.

  This takes a dict in the form of [main][builder][build], formats that URL
  and appends that to url_list. Then, it forks out and queries each build_url
  for build information.
  """
  url_list = []
  for main, builder_dict in main_builds.iteritems():
    for builder, new_builds in builder_dict.iteritems():
      for buildnum in new_builds:
        safe_builder = urllib.quote(builder)
        url = main + '/json/builders/%s/builds/%s' % (safe_builder,
                                                        buildnum)
        url_list.append((url, main, builder, buildnum))

  # Prevent map from hanging, see http://bugs.python.org/issue12157.
  if url_list:
    # The async/get is so that ctrl-c can interrupt the scans.
    # See http://stackoverflow.com/questions/1408356/
    # keyboard-interrupts-with-pythons-multiprocessing-pool
    with chromium_utils.MultiPool(processes) as pool:
      builds = filter(bool, pool.map_async(get_build_json, url_list).get(
          9999999))
  else:
    builds = []

  return builds


def propagate_build_json_to_db(build_db, builds):
  """Propagates build status changes from build_json to build_db."""
  for build_json, main, builder, buildnum in builds:
    build = build_db.mains[main].setdefault(builder, {}).get(buildnum)
    if not build:
      build = build_scan_db.gen_build()

    if build_json.get('results', None) is not None:
      build = build._replace(finished=True)  # pylint: disable=W0212
    else:
      # Builds can't be marked succeeded unless they are finished.
      build = build._replace(succeeded=False)  # pylint: disable=W0212

    build_db.mains[main][builder][buildnum] = build


def get_options():
  prog_desc = 'Scans for builds and outputs updated builds.'
  usage = '%prog [options] <one or more main urls>'
  parser = optparse.OptionParser(usage=(usage + '\n\n' + prog_desc))
  parser.add_option('--build-db', default='build_scan_db.json',
                    help='records the last-seen build for each builder')
  parser.add_option('--clear-build-db', action='store_true',
                    help='reset build_db to be empty')
  parser.add_option('--skip-build-db-update', action='store_true',
                    help='don\' write to the build_db, overridden by clear-db')
  parser.add_option('--parallelism', default=16,
                    help='up to this many builds can be queried simultaneously')
  parser.add_option('-v', '--verbose', action='store_true',
                    help='turn on extra debugging information')

  options, args = parser.parse_args()

  if not args:
    parser.error('you need to specify at least one main URL')

  args = [url.rstrip('/') for url in args]

  return options, args


def get_updated_builds(mains, build_db, parallelism):
  new_builds, main_jsons = find_new_builds_per_main(mains, build_db)
  build_jsons = get_build_jsons(new_builds, parallelism)
  propagate_build_json_to_db(build_db, build_jsons)
  return main_jsons, build_jsons


def main():
  options, args = get_options()

  logging.basicConfig(level=logging.DEBUG if options.verbose else logging.INFO)

  mains = set(args)

  if options.clear_build_db:
    build_db = {}
    build_scan_db.save_build_db(build_db, {}, options.build_db)
  else:
    build_db = build_scan_db.get_build_db(options.build_db)

  _, build_jsons = get_updated_builds(
      mains, build_db, options.parallelism)

  for _, main_url, builder, buildnum in build_jsons:
    print '%s:%s:%s' % (main_url, builder, buildnum)

  if not options.skip_build_db_update:
    build_scan_db.save_build_db(build_db, {}, options.build_db)

  return 0


if __name__ == '__main__':
  sys.exit(main())
