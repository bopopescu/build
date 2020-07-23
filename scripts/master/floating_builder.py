# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from twisted.python import log
from twisted.internet import reactor

class PokeBuilderTimer(object):
  def __init__(self, botmain, buildername):
    self.botmain = botmain
    self.buildername = buildername
    self.delayed_call = None

  def cancel(self):
    if self.delayed_call is not None:
      self.delayed_call.cancel()
      self.delayed_call = None

  def reset(self, delta):
    if self.delayed_call is not None:
      current_delta = (datetime.fromtimestamp(self.delayed_call.getTime()) -
                       datetime.datetime.now())
      if delta < current_delta:
        self.delayed_call.reset(delta.total_seconds())
      return

    # Schedule a new call
    self.delayed_call = reactor.callLater(
        delta.total_seconds(),
        self._poke,
    )

  def _poke(self):
    self.delayed_call = None
    log.msg("Poking builds for builder %r" % (self.buildername,))
    self.botmain.maybeStartBuildsForBuilder(self.buildername)


class FloatingNextSubordinateFunc(object):
  """
  This object, when used as a Builder's 'nextSubordinate' function, allows a strata-
  based preferential treatment to be assigned to a Builder's Subordinates.

  The 'nextSubordinate' function is called on a scheduled build when an associated
  subordinate becomes available, either coming online or finishing an existing build.
  These events are used as stimulus to enable the primary builder(s) to pick
  up builds when appropriate.

  1) If a Primary is available, the build will be assigned to them.
  2) If a Primary builder is busy or is still within its grace period for
    unavailability, no subordinate will be assigned in anticipation of the
    'nextSubordinate' being re-invoked once the builder returns (1). If the grace
    period expires, we "poke" the main to call 'nextSubordinate', at which point
    the build will fall through to a lower strata.
  3) If a Primary subordinate is offline past its grace period, the build will be
    assigned to a Floating subordinate.

  Args:
    strata_property: (str) The name of the Builder property to use to identify
        its strata.
    strata: (list) A list of strata values ordered by selection priority
    grace_period: (None/timedelta) If not None, the amount of time that a subordinate
        can be offline before builds fall through to a lower strata.
  """

  def __init__(self, strata_property, strata, grace_period=None):
    self._strata = tuple(strata)
    self._strata_property = strata_property
    self._grace_period = grace_period
    self._subordinate_strata_map = {}
    self._subordinate_seen_times = {}
    self._poke_builder_timers = {}
    self.verbose = False

  def __repr__(self):
    return '%s(%s)' % (type(self).__name__, ' > '.join(self._strata))

  def __call__(self, builder, subordinate_builders):
    """Main 'nextSubordinate' invocation point.

    When this is called, we are given the following information:
    - The Builder
    - A set of 'SubordinateBuilder' instances that are available and ready for
      assignment (subordinate_builders).
    - The total set of ONLINE 'SubordinateBuilder' instances associated with
      'builder' (builder.subordinates)
    - The set of all subordinates configured for Builder (via
      '_get_all_subordinate_status')

    We compile that into a stateful awareness and use it as a decision point.
    Based on the subordinate availability and grace period, we will either:
    (1) Return a subordinate immediately to claim this build
    (2) Return 'None' (delaying the build) in anticipation of a higher-strata
        subordinate becoming available.

    If we go with (2), we will schedule a 'poke' timer to stimulate a future
    'nextSubordinate' call if the only higher-strata subordinate candidates are currently
    offline. We do this because they could be permanently offline, so there's
    no guarentee that a 'nextSubordinate' will be naturally called in any time frame.
    """
    self._debug("Calling %r with builder=[%s], subordinates=[%s]",
                self, builder, subordinate_builders)
    self._cancel_builder_timer(builder)

    # Get the set of all 'SubordinateStatus' assigned to this Builder (idle, busy,
    # and offline).
    subordinate_status_map = dict(
        (subordinate_status.name, subordinate_status)
        for subordinate_status in self._get_all_subordinate_status(builder)
    )

    # Index proposed 'nextSubordinate' subordinates by name
    proposed_subordinate_builder_map = {}
    for subordinate_builder in subordinate_builders:
      proposed_subordinate_builder_map[subordinate_builder.subordinate.subordinatename] = subordinate_builder

    # Calculate the oldest a subordinate can be before we assume something's wrong.
    grace_threshold = now = None
    if self._grace_period is not None:
      now = datetime.now()
      grace_threshold = (now - self._grace_period)

    # Index all builder subordinates (even busy ones) by name. Also, record this
    # subordinate's strata so we can reference it even if the subordinate goes offline
    # in the future.
    online_subordinate_builders = set()
    for subordinate_builder in builder.subordinates:
      build_subordinate = subordinate_builder.subordinate
      if build_subordinate is None:
        continue
      self._record_strata(build_subordinate)
      if now is not None:
        self._record_subordinate_seen_time(build_subordinate, now)
      online_subordinate_builders.add(build_subordinate.subordinatename)

    # Check the strata, in order.
    for stratum in self._strata:
      busy_subordinates = []
      offline_subordinates = []
      wait_delta = None

      for subordinate_name in self._subordinate_strata_map.get(stratum, ()):
        self._debug("Considering subordinate %r for stratum %r", subordinate_name, stratum)

        # Get the 'SubordinateStatus' object for this subordinate
        subordinate_status = subordinate_status_map.get(subordinate_name)
        if subordinate_status is None:
          continue

        # Was this subordinate proposed by 'nextSubordinate'?
        subordinate_builder = proposed_subordinate_builder_map.get(subordinate_name)
        if subordinate_builder is not None:
          # Yes. Use it!
          self._debug("Subordinate %r is available", subordinate_name)
          return subordinate_builder

        # Is this subordinate online?
        if subordinate_name in online_subordinate_builders:
          # The subordinate is online, but is not proposed (BUSY); add it to the
          # desired subordinates list.
          self._debug("Subordinate %r is online but BUSY; marking preferred",
                      subordinate_name)
          busy_subordinates.append(subordinate_name)
          continue

        # The subordinate is offline; do we have a grace period?
        if grace_threshold is None:
          # No grace period, so this subordinate is not a candidate
          self._debug("Subordinate %r is OFFLINE with no grace period; ignoring",
                      subordinate_name)
          continue

        # Yes; is this subordinate within the grace period?
        last_seen = self._get_latest_seen_time(subordinate_status)
        if last_seen < grace_threshold:
          # Not within grace period, so this subordinate is out.
          self._debug("Subordinate %r is OFFLINE and outside of grace period "
                      "(%s < %s); ignoring",
                      subordinate_name, last_seen, grace_threshold)
          continue

        # This subordinate is within its grace threshold. Add it to the list of
        # desired stratum subordinates and update our wait delta in case we have to
        # poke.
        #
        # We track the longest grace period delta, since after this point if
        # no subordinates have taken the build we would otherwise hang.
        self._debug("Subordinate %r is OFFLINE but within grace period "
                    "(%s >= %s); marking preferred",
                    subordinate_name, last_seen, grace_threshold)
        offline_subordinates.append(subordinate_name)
        subordinate_wait_delta = (self._grace_period - (now - last_seen))
        if (wait_delta is None) or (subordinate_wait_delta > wait_delta):
          wait_delta = subordinate_wait_delta

      # We've looped through our stratum and found no proposed candidates. Are
      # there any preferred ones?
      if busy_subordinates or offline_subordinates:
        log.msg("Returning 'None' in anticipation of unavailable subordinates. "
                "Please disregard the following BuildBot 'nextSubordinate' "
                "error: %s" % (busy_subordinates + offline_subordinates,))

        # We're going to return 'None' to wait for a preferred subordinate. If all of
        # the subordinates that we're anticipating are offline, schedule a 'poke'
        # after the last candidate has exceeded its grace period to allow the
        # build to go to lower strata.
        if (not busy_subordinates) and (wait_delta is not None):
          self._debug("Scheduling 'ping' for %r in %s",
                      builder.name, wait_delta)
          self._schedule_builder_timer(
              builder,
              wait_delta,
          )
        return None

    self._debug("No subordinates are available; returning 'None'")
    return None

  def _debug(self, fmt, *args):
    if not self.verbose:
      return
    log.msg(fmt % args)

  @staticmethod
  def _get_all_subordinate_status(builder):
    # Try using the builder's BuilderStatus object to get a list of all subordinates
    if builder.builder_status is not None:
      return builder.builder_status.getSubordinates()

    # Satisfy with the list of currently-connected subordinates
    return [subordinate_builder.subordinate.subordinate_status
            for subordinate_builder in builder.subordinates]

  def _get_latest_seen_time(self, subordinate_status):
    times = []

    # Add all of the registered connect times
    times += [datetime.fromtimestamp(connect_time)
              for connect_time in subordinate_status.connect_times]

    # Add the time of the subordinate's last message
    times.append(datetime.fromtimestamp(subordinate_status.lastMessageReceived()))

    # Add the last time we've seen the subordinate in our 'nextSubordinate' function
    last_seen_time = self._subordinate_seen_times.get(subordinate_status.name)
    if last_seen_time is not None:
      times.append(last_seen_time)

    if not times:
      return None
    return max(times)

  def _record_strata(self, build_subordinate):
    stratum = build_subordinate.properties.getProperty(self._strata_property)
    strata_set = self._subordinate_strata_map.get(stratum)
    if strata_set is None:
      strata_set = set()
      self._subordinate_strata_map[stratum] = strata_set
    strata_set.add(build_subordinate.subordinatename)

  def _record_subordinate_seen_time(self, build_subordinate, now):
    self._subordinate_seen_times[build_subordinate.subordinatename] = now

  def _schedule_builder_timer(self, builder, delta):
    poke_builder_timer = self._poke_builder_timers.get(builder.name)
    if poke_builder_timer is None:
      poke_builder_timer = PokeBuilderTimer(
          builder.botmain,
          builder.name,
      )
      self._poke_builder_timers[builder.name] = poke_builder_timer
    poke_builder_timer.reset(delta)

  def _cancel_builder_timer(self, builder):
    poke_builder_timer = self._poke_builder_timers.get(builder.name)
    if poke_builder_timer is None:
      return
    poke_builder_timer.cancel()
