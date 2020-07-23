# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This PollingChangeSource polls pub for new versions of a given set of
packages.

Whenever there is a new version we will trigger a new change.
"""
import json

import traceback
from twisted.internet import defer
from twisted.python import log
from twisted.web.client import getPage

from buildbot.changes import base

VALUE_NOT_SET = -1

class PubPoller(base.PollingChangeSource):
  """Poll a set of pub packages for changes"""

  def __init__(self, packages, pollInterval=5*60, project=None):
    self.packages = packages
    self.pollInterval = pollInterval
    self.project = project
    log.msg("poll interval %s" % pollInterval)
    self.versions = {}

  def describe(self):
    return 'Watching pub packages %s' % self.packages

  def make_change(self, package, version):
    repo = 'http://pub.dartlang.org/packages/%s/versions' % package
    # The buildbot console has a hard time showing the correct build links
    # when there are multiple pub packages with the same version number
    # We fix this by prefix the revision with the package name
    revision = '%s-%s' % (package, version)
    self.main.addChange(author='Pub: %s' % package,
                          files=[],
                          repository=repo,
                          revlink=repo,
                          comments='Polled from %s' % package,
                          project=self.project,
                          revision=revision)

  # pub.dartlang.org is returning the versions in non sorted order
  # We simply see if there was any new versions since the last time around.
  # Normally we only see one version pushed, but since we only pull every
  # [pollInterval] seconds we may get more than one. We report these with
  # + between versions.
  @staticmethod
  def find_new_versions(old_set, new_set):
    return " + ".join(old_set - new_set)

  @defer.inlineCallbacks
  def poll(self):
    log.msg('Polling all packages on pub')
    for package in self.packages:
      try:
        pulled_versions = yield self.getVersions(package)
        count = len(pulled_versions)
        # If we could not set the initial value, set it now
        if self.versions[package] == VALUE_NOT_SET:
          log.msg('Delayed set of initial value for %s' % package)
          self.versions[package] = pulled_versions
        elif len(self.versions[package]) != count:
          log.msg('Package %s has new version' % package)
          version = self.find_new_versions(pulled_versions,
                                           self.versions[package])
          self.versions[package] = pulled_versions
          self.make_change(package, version)
      except Exception:
        log.msg('Could not get version for package %s: %s' %
                (package, traceback.format_exc()))

  def poll_package(self, package):
    poll_url = 'http://pub.dartlang.org/api/packages/%s' % package
    log.msg('Polling pub package %s from %s' % (package, poll_url))
    return getPage(poll_url, timeout=self.pollInterval)

  @defer.inlineCallbacks
  def startService(self):
    # Get initial version when starting to poll
    for package in self.packages:
      log.msg("doing initial poll for package %s" % package)
      try:
        versions = yield self.getVersions(package)
        count = len(versions)
        log.msg('Initial count for %s is %s' % (package, count))
        self.versions[package] = versions
      except Exception:
        log.msg('Could not set initial value for package %s %s' %
                (package, traceback.format_exc()))
        self.versions[package] = VALUE_NOT_SET
    base.PollingChangeSource.startService(self)

  @defer.inlineCallbacks
  def getVersions(self, package):
    info = yield self.poll_package(package)
    package_info = json.loads(info)
    defer.returnValue(
        set([package['version'] for package in package_info['versions']]))

