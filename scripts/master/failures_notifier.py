# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A StatusReceiver module to warn committers about new failures introduced.
"""

import re

from twisted.python import log

from main import build_utils
from main import chromium_notifier
from main import failures_history


class FailuresNotifier(chromium_notifier.ChromiumNotifier):
  """A status notifier that only alerts committers on new failures.

  See builder.interfaces.IStatusReceiver to have more information about the
  parameters type."""

  # Ignore failures that happened more than this number of times recently.
  _IGNORE_FAILURES_THRESHOLD = 1

  def __init__(self, **kwargs):
    # Set defaults.
    kwargs.setdefault('sheriffs', ['sheriff'])
    kwargs.setdefault('sendToInterestedUsers', True)
    if not kwargs.get('minimum_delay_between_alert'):
      kwargs['minimum_delay_between_alert'] = 0
    kwargs.setdefault(
        'status_header',
        'Failure notification for "%(steps)s" on "%(builder)s".')
    chromium_notifier.ChromiumNotifier.__init__(self, **kwargs)

    # TODO(timurrrr): Make recent_failures an optional argument.
    # We might want to use one history object for a few
    # FailuresNotifiers (e.g. "ordinary" bots + Webkit bots on Memory FYI)
    self.recent_failures = failures_history.FailuresHistory(
        expiration_time=12*3600, size_limit=1000)

  def isInterestingStep(self, build_status, step_status, results):
    """Look at most cases that could make us ignore the step results.
    """
    # If the base class thinks we're not interesting -> skip it.
    if not chromium_notifier.ChromiumNotifier.isInterestingStep(
        self, build_status, step_status, results):
      return False

    # Check if the subordinate is still alive. We should not close the tree for
    # inactive subordinates.
    subordinate_name = build_status.getSubordinatename()
    if subordinate_name in self.main_status.getSubordinateNames():
      # @type self.main_status: L{buildbot.status.builder.Status}
      # @type self.parent: L{buildbot.main.BuildMain}
      # @rtype getSubordinate(): L{buildbot.status.builder.SubordinateStatus}
      subordinate_status = self.main_status.getSubordinate(subordinate_name)
      if subordinate_status and not subordinate_status.isConnected():
        log.msg('[failurenotifier] Subordinate %s was disconnected, '
                'not sending a warning' % subordinate_name)
        return False

    # If all the failure_ids were observed in older builds then this
    # failure is not interesting. Also, store the current failure.
    has_failures_to_report = False
    for l in step_status.getLogs():
      failure = l.getName()  # stdio or suppression hash or failed test or ?

      # TODO(timurrrr): put the gtest regexp into a common place.
      if (not re.match(r'^[\dA-F]{16}$', failure) and
          not re.match(r'((\w+/)?\w+\.\w+(/\d+)?)', failure)):  # gtest name
        if failure != 'stdio':
          log.msg('[failurenotifier] Log `%s` is ignored since doesn\'t look '
                  'like a memory suppression hash or test failure.' % failure)
        continue

      if '.FLAKY_' in failure or '.FAILS_' in failure:
        log.msg('[failurenotifier] Ignoring flaky/fails tests: `%s`' % failure)
        continue

      if (self.recent_failures.GetCount(failure) <
          self._IGNORE_FAILURES_THRESHOLD):
        has_failures_to_report = True
        log.msg('[failurenotifier] Failure `%s` '
                'is interesting' % failure)
      else:
        log.msg('[failurenotifier] Failure `%s` '
                'is not interesting - happened to often recently' % failure)
      self.recent_failures.Put(failure)

    # If we don't have a version stamp nor a blame list, then this is most
    # likely a build started manually, and we don't want to issue a warning.
    #
    # This code is intentionally put after Put calls so we don't send failure
    # notifications with the wrong blamelist once bots cycle for the second time
    # after a main restart.
    latest_revision = build_utils.getLatestRevision(build_status)
    if not latest_revision or not build_status.getResponsibleUsers():
      log.msg('[failurenotifier] Subordinate %s failed, but no version stamp, '
              'so skipping.' % subordinate_name)
      return False

    if has_failures_to_report:
      log.msg('[failurenotifier] Decided to send a warning because of subordinate %s '
              'on revision %s' % (subordinate_name, str(latest_revision)))
      return True
    else:
      log.msg('[failurenotifier] Subordinate %s revision %s has no interesting '
              'failures' % (subordinate_name, str(latest_revision)))
      return False
