# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file encapsulates most of buildbot API for BuildBucketIntegrator."""

from buildbot.changes.changes import Change
from buildbot.interfaces import IControl
from buildbot.process.buildrequest import BuildRequest
from buildbot.status import builder as build_results
from twisted.internet.defer import inlineCallbacks, returnValue
import sqlalchemy as sa


class BuildRequestGateway(object):
  """Simplifies BuildRequest API for BuildBucketIntegrator."""

  def __init__(self, main, build_request=None, brid=None):
    assert main
    assert build_request is not None or brid is not None
    self.main = main
    self.build_request = build_request
    self.brid = brid
    if not self.brid and self.build_request:
      self.brid = self.build_request.id

  @inlineCallbacks
  def _ensure_build_request(self):
    if self.build_request:
      return
    assert self.brid
    brdict = yield self.main.db.buildrequests.getBuildRequest(self.brid)
    self.build_request = yield BuildRequest.fromBrdict(self.main, brdict)

  @inlineCallbacks
  def get_property(self, name):
    yield self._ensure_build_request()
    value = self.build_request.properties.getProperty(name)
    returnValue(value)

  def __str__(self):
    return 'Build request %s' % self.brid

  def __repr__(self):
    return 'BuildRequestGateway(brid=%s)' % self.brid

  @inlineCallbacks
  def cancel(self):
    yield self._ensure_build_request()
    yield self.build_request.cancelBuildRequest()

  @inlineCallbacks
  def is_failed(self):
    """Returns True if build request is marked failed in the database.

    Performs a database query, does not a cached value.
    """
    brdict = yield self.main.db.buildrequests.getBuildRequest(self.brid)
    returnValue(
        brdict.get('complete', False) and
        brdict.get('results') == build_results.FAILURE
    )

  @inlineCallbacks
  def has_builds(self):
    builds = yield self.main.db.builds.getBuildsForRequest(self.brid)
    returnValue(bool(builds))


class BuildbotGateway(object):
  """All buildbot APIs needed by BuildBucketIntegrator to function.

  Handy to mock.
  """

  def __init__(self, main):
    """Creates a BuildbotGateway.

    Args:
      main (buildbot.main.BuildMain): the buildbot main.
    """
    assert main, 'main not specified'
    self.main = main

  def find_changes_by_revision(self, revision):
    """Searches for Changes in database by |revision| and returns change ids."""
    def find(conn):
      table = self.main.db.model.changes
      q = sa.select([table.c.changeid]).where(table.c.revision == revision)
      return [row.changeid for row in conn.execute(q)]
    return self.main.db.pool.do(find)

  @inlineCallbacks
  def get_change_by_id(self, change_id):
    """Returns buildot.changes.changes.Change as Deferred for |change_id|."""
    chdict = yield self.main.db.changes.getChange(change_id)
    change = yield Change.fromChdict(self.main, chdict)
    returnValue(change)

  def get_cache(self, name, miss_fn):
    """Returns a buildbot.util.lru.AsyncLRUCache by |name|.

    Args:
      name (str): cache name. If called twice with the same name, returns the
        same object.
      miss_fn (func): function cache_key -> value. Used on cache miss.
    """
    return self.main.caches.get_cache(name, miss_fn)

  def add_change_to_db(self, **kwargs):
    """Adds a change to buildbot database.

    See buildbot.db.changes.ChangesConnectorComponent.addChange for arguments.
    """
    return self.main.db.changes.addChange(**kwargs)

  def insert_source_stamp_to_db(self, **kwargs):
    """Inserts a SourceStamp to buildbot database.

    See buildbot.db.sourcestamps.SourceStampsConnectorComponent.addSourceStamp
    for arguments.
    """
    return self.main.db.sourcestamps.addSourceStamp(**kwargs)

  def get_builders(self):
    """Returns a map of builderName -> buildbot.status.builder.BuilderStatus."""
    status = self.main.getStatus()
    names = status.getBuilderNames()
    return {name:status.getBuilder(name) for name in names}

  def get_subordinates(self):
    """Returns a list of all subordinates.

    Returns:
      A list of buildbot.status.subordinate.SubordinateStatus.
    """
    status = self.main.getStatus()
    return map(status.getSubordinate, status.getSubordinateNames())

  def get_connected_subordinates(self):
    """Returns a list of all connected subordinates.

    Returns:
      A list of buildbot.status.subordinate.SubordinateStatus.
    """
    return filter(lambda s: s.isConnected(), self.get_subordinates())

  @inlineCallbacks
  def add_build_request(
      self, ssid, reason, builder_name, properties_with_source,
      external_idstring):
    """Adds a build request to buildbot database."""
    _, brids = yield self.main.addBuildset(
        ssid=ssid,
        reason=reason,
        builderNames=[builder_name],
        properties=properties_with_source,
        external_idstring=external_idstring,
    )
    assert len(brids) == 1
    returnValue(BuildRequestGateway(self.main, brid=brids[builder_name]))

  @inlineCallbacks
  def get_incomplete_build_requests(self):
    """Returns not yet completed build requests from the database as Deferred.

    Does not return build requests for non-existing builders.
    """
    build_request_dicts = yield self.main.db.buildrequests.getBuildRequests(
        complete=False,
        buildername=self.main.getStatus().getBuilderNames())
    requests = []
    for brdict in build_request_dicts:
      # TODO(nodir): optimize: run these queries in parallel.
      req = yield BuildRequest.fromBrdict(self.main, brdict)
      requests.append(BuildRequestGateway(self.main, build_request=req))
    returnValue(requests)

  def get_build_url(self, build):
    """Returns a URL for the |build|."""
    return self.main.getStatus().getURLForThing(build)

  def stop_build(self, build, reason):
    """Stops the |build|."""
    control = IControl(self.main)  # request IControl from self.main.
    builder_control = control.getBuilder(build.getBuilder().getName())
    assert builder_control
    build_control = builder_control.getBuild(build.getNumber())
    assert build_control
    build_control.stopBuild(reason)
