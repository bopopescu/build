# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import random, weakref
from zope.interface import implements
from twisted.python import log, failure
from twisted.spread import pb
from twisted.application import service, internet
from twisted.internet import defer

from buildbot import interfaces
from buildbot.status.progress import Expectations
from buildbot.status.builder import RETRY
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.process.properties import Properties
from buildbot.process import buildrequest, subordinatebuilder
from buildbot.process.subordinatebuilder import BUILDING
from buildbot.db import buildrequests

class Builder(pb.Referenceable, service.MultiService):
    """I manage all Builds of a given type.

    Each Builder is created by an entry in the config file (the c['builders']
    list), with a number of parameters.

    One of these parameters is the L{buildbot.process.factory.BuildFactory}
    object that is associated with this Builder. The factory is responsible
    for creating new L{Build<buildbot.process.build.Build>} objects. Each
    Build object defines when and how the build is performed, so a new
    Factory or Builder should be defined to control this behavior.

    The Builder holds on to a number of L{BuildRequest} objects in a
    list named C{.buildable}. Incoming BuildRequest objects will be added to
    this list, or (if possible) merged into an existing request. When a subordinate
    becomes available, I will use my C{BuildFactory} to turn the request into
    a new C{Build} object. The C{BuildRequest} is forgotten, the C{Build}
    goes into C{.building} while it runs. Once the build finishes, I will
    discard it.

    I maintain a list of available SubordinateBuilders, one for each connected
    subordinate that the C{subordinatenames} parameter says we can use. Some of these
    will be idle, some of them will be busy running builds for me. If there
    are multiple subordinates, I can run multiple builds at once.

    I also manage forced builds, progress expectation (ETA) management, and
    some status delivery chores.

    @type buildable: list of L{buildbot.process.buildrequest.BuildRequest}
    @ivar buildable: BuildRequests that are ready to build, but which are
                     waiting for a buildsubordinate to be available.

    @type building: list of L{buildbot.process.build.Build}
    @ivar building: Builds that are actively running

    @type subordinates: list of L{buildbot.buildsubordinate.BuildSubordinate} objects
    @ivar subordinates: the subordinates currently available for building
    """

    expectations = None # this is created the first time we get a good build

    def __init__(self, setup, builder_status):
        """
        @type  setup: dict
        @param setup: builder setup data, as stored in
                      BuildmainConfig['builders'].  Contains name,
                      subordinatename(s), builddir, subordinatebuilddir, factory, locks.
        @type  builder_status: L{buildbot.status.builder.BuilderStatus}
        """
        service.MultiService.__init__(self)
        self.name = setup['name']
        self.subordinatenames = []
        if setup.has_key('subordinatename'):
            self.subordinatenames.append(setup['subordinatename'])
        if setup.has_key('subordinatenames'):
            self.subordinatenames.extend(setup['subordinatenames'])
        self.builddir = setup['builddir']
        self.subordinatebuilddir = setup['subordinatebuilddir']
        self.buildFactory = setup['factory']
        self.nextSubordinate = setup.get('nextSubordinate')
        if self.nextSubordinate is not None and not callable(self.nextSubordinate):
            raise ValueError("nextSubordinate must be callable")
        self.locks = setup.get("locks", [])
        self.env = setup.get('env', {})
        assert isinstance(self.env, dict)
        if setup.has_key('periodicBuildTime'):
            raise ValueError("periodicBuildTime can no longer be defined as"
                             " part of the Builder: use scheduler.Periodic"
                             " instead")
        self.nextBuild = setup.get('nextBuild')
        if self.nextBuild is not None and not callable(self.nextBuild):
            raise ValueError("nextBuild must be callable")
        self.nextSubordinateAndBuild = setup.get('nextSubordinateAndBuild')
        if self.nextSubordinateAndBuild is not None:
            if not callable(self.nextSubordinateAndBuild):
                raise ValueError("nextSubordinateAndBuild must be callable")
            if self.nextBuild or self.nextSubordinate:
                raise ValueError("nextSubordinateAndBuild cannot be specified"
                                 " together with either nextSubordinate or nextBuild")

        self.buildHorizon = setup.get('buildHorizon')
        self.logHorizon = setup.get('logHorizon')
        self.eventHorizon = setup.get('eventHorizon')
        self.mergeRequests = setup.get('mergeRequests')
        self.properties = setup.get('properties', {})
        self.category = setup.get('category', None)

        # build/wannabuild slots: Build objects move along this sequence
        self.building = []
        # old_building holds active builds that were stolen from a predecessor
        self.old_building = weakref.WeakKeyDictionary()

        # buildsubordinates which have connected but which are not yet available.
        # These are always in the ATTACHING state.
        self.attaching_subordinates = []

        # buildsubordinates at our disposal. Each SubordinateBuilder instance has a
        # .state that is IDLE, PINGING, or BUILDING. "PINGING" is used when a
        # Build is about to start, to make sure that they're still alive.
        self.subordinates = []

        self.builder_status = builder_status
        self.builder_status.setSubordinatenames(self.subordinatenames)
        self.builder_status.buildHorizon = self.buildHorizon
        self.builder_status.logHorizon = self.logHorizon
        self.builder_status.eventHorizon = self.eventHorizon

        self.reclaim_svc = internet.TimerService(10*60, self.reclaimAllBuilds)
        self.reclaim_svc.setServiceParent(self)

        # for testing, to help synchronize tests
        self.run_count = 0

    def stopService(self):
        d = defer.maybeDeferred(lambda :
                service.MultiService.stopService(self))
        def flushMaybeStartBuilds(_):
            # at this point, self.running = False, so another maybeStartBuilds
            # invocation won't hurt anything, but it also will not complete
            # until any currently-running invocations are done.
            return self.maybeStartBuild()
        d.addCallback(flushMaybeStartBuilds)
        return d

    def setBotmain(self, botmain):
        self.botmain = botmain
        self.main = botmain.main
        self.db = self.main.db
        self.main_name = self.main.main_name
        self.main_incarnation = self.main.main_incarnation

    def compareToSetup(self, setup):
        diffs = []
        setup_subordinatenames = []
        if setup.has_key('subordinatename'):
            setup_subordinatenames.append(setup['subordinatename'])
        setup_subordinatenames.extend(setup.get('subordinatenames', []))
        if setup_subordinatenames != self.subordinatenames:
            diffs.append('subordinatenames changed from %s to %s' \
                         % (self.subordinatenames, setup_subordinatenames))
        if setup['builddir'] != self.builddir:
            diffs.append('builddir changed from %s to %s' \
                         % (self.builddir, setup['builddir']))
        if setup['subordinatebuilddir'] != self.subordinatebuilddir:
            diffs.append('subordinatebuilddir changed from %s to %s' \
                         % (self.subordinatebuilddir, setup['subordinatebuilddir']))
        if setup['factory'] != self.buildFactory: # compare objects
            diffs.append('factory changed')
        if setup.get('locks', []) != self.locks:
            diffs.append('locks changed from %s to %s' % (self.locks, setup.get('locks')))
        if setup.get('env', {}) != self.env:
            diffs.append('env changed from %s to %s' % (self.env, setup.get('env', {})))
        if setup.get('nextSubordinate') != self.nextSubordinate:
            diffs.append('nextSubordinate changed from %s to %s' % (self.nextSubordinate, setup.get('nextSubordinate')))
        if setup.get('nextBuild') != self.nextBuild:
            diffs.append('nextBuild changed from %s to %s' % (self.nextBuild, setup.get('nextBuild')))
        if setup.get('nextSubordinateAndBuild') != self.nextSubordinateAndBuild:
            diffs.append('nextSubordinateAndBuild changed from %s to %s' % (self.nextSubordinateAndBuild, setup.get('nextSubordinateAndBuild')))
        if setup.get('buildHorizon', None) != self.buildHorizon:
            diffs.append('buildHorizon changed from %s to %s' % (self.buildHorizon, setup['buildHorizon']))
        if setup.get('logHorizon', None) != self.logHorizon:
            diffs.append('logHorizon changed from %s to %s' % (self.logHorizon, setup['logHorizon']))
        if setup.get('eventHorizon', None) != self.eventHorizon:
            diffs.append('eventHorizon changed from %s to %s' % (self.eventHorizon, setup['eventHorizon']))
        if setup.get('category', None) != self.category:
            diffs.append('category changed from %r to %r' % (self.category, setup.get('category', None)))

        return diffs

    def __repr__(self):
        return "<Builder '%r' at %d>" % (self.name, id(self))

    @defer.deferredGenerator
    def getOldestRequestTime(self):

        """Returns the submitted_at of the oldest unclaimed build request for
        this builder, or None if there are no build requests.

        @returns: datetime instance or None, via Deferred
        """
        wfd = defer.waitForDeferred(
            self.main.db.buildrequests.getBuildRequests(
                        buildername=self.name, claimed=False))
        yield wfd
        unclaimed = wfd.getResult()

        if unclaimed:
            unclaimed = [ brd['submitted_at'] for brd in unclaimed ]
            unclaimed.sort()
            yield unclaimed[0]
        else:
            yield None

    def consumeTheSoulOfYourPredecessor(self, old):
        """Suck the brain out of an old Builder.

        This takes all the runtime state from an existing Builder and moves
        it into ourselves. This is used when a Builder is changed in the
        main.cfg file: the new Builder has a different factory, but we want
        all the builds that were queued for the old one to get processed by
        the new one. Any builds which are already running will keep running.
        The new Builder will get as many of the old SubordinateBuilder objects as
        it wants."""

        log.msg("consumeTheSoulOfYourPredecessor: %s feeding upon %s" %
                (self, old))
        # all pending builds are stored in the DB, so we don't have to do
        # anything to claim them. The old builder will be stopService'd,
        # which should make sure they don't start any new work

        # this is kind of silly, but the builder status doesn't get updated
        # when the config changes, yet it stores the category.  So:
        self.builder_status.category = self.category

        # old.building (i.e. builds which are still running) is not migrated
        # directly: it keeps track of builds which were in progress in the
        # old Builder. When those builds finish, the old Builder will be
        # notified, not us. However, since the old SubordinateBuilder will point to
        # us, it is our maybeStartBuild() that will be triggered.
        if old.building:
            self.builder_status.setBigState("building")
        # however, we do grab a weakref to the active builds, so that our
        # BuilderControl can see them and stop them. We use a weakref because
        # we aren't the one to get notified, so there isn't a convenient
        # place to remove it from self.building .
        for b in old.building:
            self.old_building[b] = None
        for b in old.old_building:
            self.old_building[b] = None

        # Our set of subordinatenames may be different. Steal any of the old
        # buildsubordinates that we want to keep using.
        for sb in old.subordinates[:]:
            if sb.subordinate.subordinatename in self.subordinatenames:
                log.msg(" stealing buildsubordinate %s" % sb)
                self.subordinates.append(sb)
                old.subordinates.remove(sb)
                sb.setBuilder(self)

        # old.attaching_subordinates:
        #  these SubordinateBuilders are waiting on a sequence of calls:
        #  remote.setMain and remote.print . When these two complete,
        #  old._attached will be fired, which will add a 'connect' event to
        #  the builder_status and try to start a build. However, we've pulled
        #  everything out of the old builder's queue, so it will have no work
        #  to do. The outstanding remote.setMain/print call will be holding
        #  the last reference to the old builder, so it will disappear just
        #  after that response comes back.
        #
        #  The BotMain will ask the subordinate to re-set their list of Builders
        #  shortly after this function returns, which will cause our
        #  attached() method to be fired with a bunch of references to remote
        #  SubordinateBuilders, some of which we already have (by stealing them
        #  from the old Builder), some of which will be new. The new ones
        #  will be re-attached.

        #  Therefore, we don't need to do anything about old.attaching_subordinates

        return # all done

    def reclaimAllBuilds(self):
        brids = set()
        for b in self.building:
            brids.update([br.id for br in b.requests])
        for b in self.old_building:
            brids.update([br.id for br in b.requests])

        if not brids:
            return defer.succeed(None)

        d = self.main.db.buildrequests.claimBuildRequests(brids)
        d.addErrback(log.err, 'while re-claiming running BuildRequests')
        return d

    def getBuild(self, number):
        for b in self.building:
            if b.build_status and b.build_status.number == number:
                return b
        for b in self.old_building.keys():
            if b.build_status and b.build_status.number == number:
                return b
        return None

    def addLatentSubordinate(self, subordinate):
        assert interfaces.ILatentBuildSubordinate.providedBy(subordinate)
        for s in self.subordinates:
            if s == subordinate:
                break
        else:
            sb = subordinatebuilder.LatentSubordinateBuilder(subordinate, self)
            self.builder_status.addPointEvent(
                ['added', 'latent', subordinate.subordinatename])
            self.subordinates.append(sb)
            self.botmain.maybeStartBuildsForBuilder(self.name)

    def attached(self, subordinate, remote, commands):
        """This is invoked by the BuildSubordinate when the self.subordinatename bot
        registers their builder.

        @type  subordinate: L{buildbot.buildsubordinate.BuildSubordinate}
        @param subordinate: the BuildSubordinate that represents the buildsubordinate as a whole
        @type  remote: L{twisted.spread.pb.RemoteReference}
        @param remote: a reference to the L{buildbot.subordinate.bot.SubordinateBuilder}
        @type  commands: dict: string -> string, or None
        @param commands: provides the subordinate's version of each RemoteCommand

        @rtype:  L{twisted.internet.defer.Deferred}
        @return: a Deferred that fires (with 'self') when the subordinate-side
                 builder is fully attached and ready to accept commands.
        """
        for s in self.attaching_subordinates + self.subordinates:
            if s.subordinate == subordinate:
                # already attached to them. This is fairly common, since
                # attached() gets called each time we receive the builder
                # list from the subordinate, and we ask for it each time we add or
                # remove a builder. So if the subordinate is hosting builders
                # A,B,C, and the config file changes A, we'll remove A and
                # re-add it, triggering two builder-list requests, getting
                # two redundant calls to attached() for B, and another two
                # for C.
                #
                # Therefore, when we see that we're already attached, we can
                # just ignore it.
                return defer.succeed(self)

        sb = subordinatebuilder.SubordinateBuilder()
        sb.setBuilder(self)
        self.attaching_subordinates.append(sb)
        d = sb.attached(subordinate, remote, commands)
        d.addCallback(self._attached)
        d.addErrback(self._not_attached, subordinate)
        return d

    def _attached(self, sb):
        self.builder_status.addPointEvent(['connect', sb.subordinate.subordinatename])
        self.attaching_subordinates.remove(sb)
        self.subordinates.append(sb)

        self.updateBigStatus()

        return self

    def _not_attached(self, why, subordinate):
        # already log.err'ed by SubordinateBuilder._attachFailure
        # TODO: remove from self.subordinates (except that detached() should get
        #       run first, right?)
        log.err(why, 'subordinate failed to attach')
        self.builder_status.addPointEvent(['failed', 'connect',
                                           subordinate.subordinatename])
        # TODO: add an HTMLLogFile of the exception

    def detached(self, subordinate):
        """This is called when the connection to the bot is lost."""
        for sb in self.attaching_subordinates + self.subordinates:
            if sb.subordinate == subordinate:
                break
        else:
            log.msg("WEIRD: Builder.detached(%s) (%s)"
                    " not in attaching_subordinates(%s)"
                    " or subordinates(%s)" % (subordinate, subordinate.subordinatename,
                                        self.attaching_subordinates,
                                        self.subordinates))
            return
        if sb.state == BUILDING:
            # the Build's .lostRemote method (invoked by a notifyOnDisconnect
            # handler) will cause the Build to be stopped, probably right
            # after the notifyOnDisconnect that invoked us finishes running.
            pass

        if sb in self.attaching_subordinates:
            self.attaching_subordinates.remove(sb)
        if sb in self.subordinates:
            self.subordinates.remove(sb)

        self.builder_status.addPointEvent(['disconnect', subordinate.subordinatename])
        sb.detached() # inform the SubordinateBuilder that their subordinate went away
        self.updateBigStatus()

    def updateBigStatus(self):
        if not self.subordinates:
            self.builder_status.setBigState("offline")
        elif self.building:
            self.builder_status.setBigState("building")
        else:
            self.builder_status.setBigState("idle")

    @defer.deferredGenerator
    def _startBuildFor(self, subordinatebuilder, buildrequests):
        """Start a build on the given subordinate.
        @param build: the L{base.Build} to start
        @param sb: the L{SubordinateBuilder} which will host this build

        @return: a Deferred which fires with a
        L{buildbot.interfaces.IBuildControl} that can be used to stop the
        Build, or to access a L{buildbot.interfaces.IBuildStatus} which will
        watch the Build as it runs. """

        build = self.buildFactory.newBuild(buildrequests)
        build.setBuilder(self)
        build.setLocks(self.locks)
        if len(self.env) > 0:
            build.setSubordinateEnvironment(self.env)

        self.building.append(build)
        self.updateBigStatus()
        log.msg("starting build %s using subordinate %s" % (build, subordinatebuilder))

        wfd = defer.waitForDeferred(
                subordinatebuilder.prepare(self.builder_status, build))
        yield wfd
        ready = wfd.getResult()

        # If prepare returns True then it is ready and we start a build
        # If it returns false then we don't start a new build.
        if not ready:
            log.msg("subordinate %s can't build %s after all; re-queueing the "
                    "request" % (build, subordinatebuilder))

            self.building.remove(build)
            if subordinatebuilder.subordinate:
                subordinatebuilder.subordinate.releaseLocks()

            # release the buildrequest claims
            wfd = defer.waitForDeferred(
                self._resubmit_buildreqs(build))
            yield wfd
            wfd.getResult()

            self.updateBigStatus()

            # and try starting builds again.  If we still have a working subordinate,
            # then this may re-claim the same buildrequests
            self.botmain.maybeStartBuildsForBuilder(self.name)

            return

        # ping the subordinate to make sure they're still there. If they've
        # fallen off the map (due to a NAT timeout or something), this
        # will fail in a couple of minutes, depending upon the TCP
        # timeout.
        #
        # TODO: This can unnecessarily suspend the starting of a build, in
        # situations where the subordinate is live but is pushing lots of data to
        # us in a build.
        log.msg("starting build %s.. pinging the subordinate %s"
                % (build, subordinatebuilder))
        wfd = defer.waitForDeferred(
                subordinatebuilder.ping())
        yield wfd
        ping_success = wfd.getResult()

        if not ping_success:
            self._startBuildFailed("subordinate ping failed", build, subordinatebuilder)
            return

        # The buildsubordinate is ready to go. subordinatebuilder.buildStarted() sets its
        # state to BUILDING (so we won't try to use it for any other builds).
        # This gets set back to IDLE by the Build itself when it finishes.
        subordinatebuilder.buildStarted()
        try:
            wfd = defer.waitForDeferred(
                    subordinatebuilder.remote.callRemote("startBuild"))
            yield wfd
            wfd.getResult()
        except:
            self._startBuildFailed(failure.Failure(), build, subordinatebuilder)
            return

        # create the BuildStatus object that goes with the Build
        bs = self.builder_status.newBuild()

        # record in the db - one per buildrequest
        bids = []
        for req in build.requests:
            wfd = defer.waitForDeferred(
                self.main.db.builds.addBuild(req.id, bs.number))
            yield wfd
            bids.append(wfd.getResult())

        # let status know
        self.main.status.build_started(req.id, self.name, bs.number)

        # start the build. This will first set up the steps, then tell the
        # BuildStatus that it has started, which will announce it to the world
        # (through our BuilderStatus object, which is its parent).  Finally it
        # will start the actual build process.  This is done with a fresh
        # Deferred since _startBuildFor should not wait until the build is
        # finished.
        d = build.startBuild(bs, self.expectations, subordinatebuilder)
        d.addCallback(self.buildFinished, subordinatebuilder, bids)
        # this shouldn't happen. if it does, the subordinate will be wedged
        d.addErrback(log.err)

        # make sure the builder's status is represented correctly
        self.updateBigStatus()

        # yield the IBuildControl, in case anyone needs it
        yield build

    def _startBuildFailed(self, why, build, subordinatebuilder):
        # put the build back on the buildable list
        log.msg("I tried to tell the subordinate that the build %s started, but "
                "remote_startBuild failed: %s" % (build, why))
        # release the subordinate. This will queue a call to maybeStartBuild, which
        # will fire after other notifyOnDisconnect handlers have marked the
        # subordinate as disconnected (so we don't try to use it again).
        subordinatebuilder.buildFinished()

        self.updateBigStatus()

        log.msg("re-queueing the BuildRequest")
        self.building.remove(build)
        self._resubmit_buildreqs(build).addErrback(log.err)

    def setupProperties(self, props):
        props.setProperty("buildername", self.name, "Builder")
        if len(self.properties) > 0:
            for propertyname in self.properties:
                props.setProperty(propertyname, self.properties[propertyname],
                                  "Builder")

    def buildFinished(self, build, sb, bids):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the subordinate,
        # which will trigger a check for any now-possible build requests
        # (maybeStartBuilds)

        # mark the builds as finished, although since nothing ever reads this
        # table, it's not too important that it complete successfully
        d = self.db.builds.finishBuilds(bids)
        d.addErrback(log.err, 'while marking builds as finished (ignored)')

        results = build.build_status.getResults()
        self.building.remove(build)
        if results == RETRY:
            self._resubmit_buildreqs(build).addErrback(log.err)
        else:
            brids = [br.id for br in build.requests]
            db = self.main.db
            d = db.buildrequests.completeBuildRequests(brids, results)
            d.addCallback(
                lambda _ : self._maybeBuildsetsComplete(build.requests))
            # nothing in particular to do with this deferred, so just log it if
            # it fails..
            d.addErrback(log.err, 'while marking build requests as completed')

        if sb.subordinate:
            sb.subordinate.releaseLocks()

        self.updateBigStatus()

    @defer.deferredGenerator
    def _maybeBuildsetsComplete(self, requests):
        # inform the main that we may have completed a number of buildsets
        for br in requests:
            wfd = defer.waitForDeferred(
                self.main.maybeBuildsetComplete(br.bsid))
            yield wfd
            wfd.getResult()

    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        return self.db.buildrequests.unclaimBuildRequests(brids)

    def setExpectations(self, progress):
        """Mark the build as successful and update expectations for the next
        build. Only call this when the build did not fail in any way that
        would invalidate the time expectations generated by it. (if the
        compile failed and thus terminated early, we can't use the last
        build to predict how long the next one will take).
        """
        if self.expectations:
            self.expectations.update(progress)
        else:
            # the first time we get a good build, create our Expectations
            # based upon its results
            self.expectations = Expectations(progress)
        log.msg("new expectations: %s seconds" % \
                self.expectations.expectedBuildTime())

    # Build Creation

    def _checkSubordinateBuilder(self, subordinatebuilder, available_subordinatebuilders):
        if subordinatebuilder not in available_subordinatebuilders:
            next_func = 'nextSubordinate'
            if self.nextSubordinateAndBuild:
                next_func = 'nextSubordinateAndBuild'
            log.msg("%s chose a nonexistent subordinate for builder '%s'; cannot"
                    " start build" % (next_func, self.name))
            return False
        return True

    def _checkBrDict(self, brdict, unclaimed_requests):
        if brdict not in unclaimed_requests:
            next_func = 'nextBuild'
            if self.nextSubordinateAndBuild:
                next_func = 'nextSubordinateAndBuild'
            log.msg("%s chose a nonexistent request for builder '%s'; cannot"
                    " start build" % (next_func, self.name))
            return False
        return True

    @defer.deferredGenerator
    def maybeStartBuild(self):
        # This method is called by the botmain whenever this builder should
        # check for and potentially start new builds.  Do not call this method
        # directly - use main.botmain.maybeStartBuildsForBuilder, or one
        # of the other similar methods if more appropriate

        # first, if we're not running, then don't start builds; stopService
        # uses this to ensure that any ongoing maybeStartBuild invocations
        # are complete before it stops.
        if not self.running:
            return

        # Check for available subordinates.  If there are no available subordinates, then
        # there is no sense continuing
        available_subordinatebuilders = [ sb for sb in self.subordinates
                                    if sb.isAvailable() ]
        if not available_subordinatebuilders:
            self.updateBigStatus()
            return

        # now, get the available build requests
        wfd = defer.waitForDeferred(
                self.main.db.buildrequests.getBuildRequests(
                        buildername=self.name, claimed=False))
        yield wfd
        unclaimed_requests = wfd.getResult()

        if not unclaimed_requests:
            self.updateBigStatus()
            return

        # sort by submitted_at, so the first is the oldest
        unclaimed_requests.sort(key=lambda brd : brd['submitted_at'])

        # get the mergeRequests function for later
        mergeRequests_fn = self._getMergeRequestsFn()

        # match them up until we're out of options
        while available_subordinatebuilders and unclaimed_requests:
            brdict = None
            if self.nextSubordinateAndBuild:
                # convert brdicts to BuildRequest objects
                wfd = defer.waitForDeferred(
                        defer.gatherResults([self._brdictToBuildRequest(brdict)
                                             for brdict in unclaimed_requests]))
                yield wfd
                breqs = wfd.getResult()

                wfd = defer.waitForDeferred(defer.maybeDeferred(
                        self.nextSubordinateAndBuild,
                        available_subordinatebuilders,
                        breqs))
                yield wfd
                subordinatebuilder, br = wfd.getResult()

                # Find the corresponding brdict for the returned BuildRequest
                if br:
                    for brdict_i in unclaimed_requests:
                       if brdict_i['brid'] == br.id:
                           brdict = brdict_i
                           break

                if (not self._checkSubordinateBuilder(subordinatebuilder,
                                                available_subordinatebuilders)
                    or not self._checkBrDict(brdict, unclaimed_requests)):
                    break
            else:
                # first, choose a subordinate (using nextSubordinate)
                wfd = defer.waitForDeferred(
                    self._chooseSubordinate(available_subordinatebuilders))
                yield wfd
                subordinatebuilder = wfd.getResult()

                if not self._checkSubordinateBuilder(subordinatebuilder,
                                               available_subordinatebuilders):
                    break

                # then choose a request (using nextBuild)
                wfd = defer.waitForDeferred(
                    self._chooseBuild(unclaimed_requests))
                yield wfd
                brdict = wfd.getResult()

                if not self._checkBrDict(brdict, unclaimed_requests):
                    break

            # merge the chosen request with any compatible requests in the
            # queue
            wfd = defer.waitForDeferred(
                self._mergeRequests(brdict, unclaimed_requests,
                                    mergeRequests_fn))
            yield wfd
            brdicts = wfd.getResult()

            # try to claim the build requests
            try:
                wfd = defer.waitForDeferred(
                        self.main.db.buildrequests.claimBuildRequests(
                            [ brdict['brid'] for brdict in brdicts ]))
                yield wfd
                wfd.getResult()
            except buildrequests.AlreadyClaimedError:
                # one or more of the build requests was already claimed;
                # re-fetch the now-partially-claimed build requests and keep
                # trying to match them
                self._breakBrdictRefloops(unclaimed_requests)
                wfd = defer.waitForDeferred(
                        self.main.db.buildrequests.getBuildRequests(
                                buildername=self.name, claimed=False))
                yield wfd
                unclaimed_requests = wfd.getResult()

                # go around the loop again
                continue

            # claim was successful, so initiate a build for this set of
            # requests.  Note that if the build fails from here on out (e.g.,
            # because a subordinate has failed), it will be handled outside of this
            # loop. TODO: test that!

            # _startBuildFor expects BuildRequest objects, so cook some up
            wfd = defer.waitForDeferred(
                    defer.gatherResults([ self._brdictToBuildRequest(brdict)
                                          for brdict in brdicts ]))
            yield wfd
            breqs = wfd.getResult()
            self._startBuildFor(subordinatebuilder, breqs)

            # and finally remove the buildrequests and subordinatebuilder from the
            # respective queues
            self._breakBrdictRefloops(brdicts)
            for brdict in brdicts:
                unclaimed_requests.remove(brdict)
            available_subordinatebuilders.remove(subordinatebuilder)

        self._breakBrdictRefloops(unclaimed_requests)
        self.updateBigStatus()
        return

    # a few utility functions to make the maybeStartBuild a bit shorter and
    # easier to read

    def _chooseSubordinate(self, available_subordinatebuilders):
        """
        Choose the next subordinate, using the C{nextSubordinate} configuration if
        available, and falling back to C{random.choice} otherwise.

        @param available_subordinatebuilders: list of subordinatebuilders to choose from
        @returns: SubordinateBuilder or None via Deferred
        """
        if self.nextSubordinate:
            return defer.maybeDeferred(lambda :
                    self.nextSubordinate(self, available_subordinatebuilders))
        else:
            return defer.succeed(random.choice(available_subordinatebuilders))

    def _chooseBuild(self, buildrequests):
        """
        Choose the next build from the given set of build requests (represented
        as dictionaries).  Defaults to returning the first request (earliest
        submitted).

        @param buildrequests: sorted list of build request dictionaries
        @returns: a build request dictionary or None via Deferred
        """
        if self.nextBuild:
            # nextBuild expects BuildRequest objects, so instantiate them here
            # and cache them in the dictionaries
            d = defer.gatherResults([ self._brdictToBuildRequest(brdict)
                                      for brdict in buildrequests ])
            d.addCallback(lambda requestobjects :
                    self.nextBuild(self, requestobjects))
            def to_brdict(brobj):
                # get the brdict for this object back
                return brobj.brdict
            d.addCallback(to_brdict)
            return d
        else:
            return defer.succeed(buildrequests[0])

    def _getMergeRequestsFn(self):
        """Helper function to determine which mergeRequests function to use
        from L{_mergeRequests}, or None for no merging"""
        # first, seek through builder, global, and the default
        mergeRequests_fn = self.mergeRequests
        if mergeRequests_fn is None:
            mergeRequests_fn = self.main.botmain.mergeRequests
        if mergeRequests_fn is None:
            mergeRequests_fn = True

        # then translate False and True properly
        if mergeRequests_fn is False:
            mergeRequests_fn = None
        elif mergeRequests_fn is True:
            mergeRequests_fn = buildrequest.BuildRequest.canBeMergedWith

        return mergeRequests_fn

    @defer.deferredGenerator
    def _mergeRequests(self, breq, unclaimed_requests, mergeRequests_fn):
        """Use C{mergeRequests_fn} to merge C{breq} against
        C{unclaimed_requests}, where both are build request dictionaries"""
        # short circuit if there is no merging to do
        if not mergeRequests_fn or len(unclaimed_requests) == 1:
            yield [ breq ]
            return

        # we'll need BuildRequest objects, so get those first
        wfd = defer.waitForDeferred(
            defer.gatherResults(
                [ self._brdictToBuildRequest(brdict)
                  for brdict in unclaimed_requests ]))
        yield wfd
        unclaimed_request_objects = wfd.getResult()
        breq_object = unclaimed_request_objects.pop(
                unclaimed_requests.index(breq))

        # gather the mergeable requests
        merged_request_objects = [breq_object]
        for other_breq_object in unclaimed_request_objects:
            wfd = defer.waitForDeferred(
                defer.maybeDeferred(lambda :
                    mergeRequests_fn(breq_object, other_breq_object)))
            yield wfd
            if wfd.getResult():
                merged_request_objects.append(other_breq_object)

        # convert them back to brdicts and return
        merged_requests = [ br.brdict for br in merged_request_objects ]
        yield merged_requests

    def _brdictToBuildRequest(self, brdict):
        """
        Convert a build request dictionary to a L{buildrequest.BuildRequest}
        object, caching the result in the dictionary itself.  The resulting
        buildrequest will have a C{brdict} attribute pointing back to this
        dictionary.

        Note that this does not perform any locking - be careful that it is
        only called once at a time for each build request dictionary.

        @param brdict: dictionary to convert

        @returns: L{buildrequest.BuildRequest} via Deferred
        """
        if 'brobj' in brdict:
            return defer.succeed(brdict['brobj'])
        d = buildrequest.BuildRequest.fromBrdict(self.main, brdict)
        def keep(buildrequest):
            brdict['brobj'] = buildrequest
            buildrequest.brdict = brdict
            return buildrequest
        d.addCallback(keep)
        return d

    def _breakBrdictRefloops(self, requests):
        """Break the reference loops created by L{_brdictToBuildRequest}"""
        for brdict in requests:
            try:
                del brdict['brobj'].brdict
            except KeyError:
                pass


class BuilderControl:
    implements(interfaces.IBuilderControl)

    def __init__(self, builder, main):
        self.original = builder
        self.main = main

    def submitBuildRequest(self, ss, reason, props=None):
        d = ss.getSourceStampId(self.main.main)
        def add_buildset(ssid):
            return self.main.main.addBuildset(
                    builderNames=[self.original.name],
                    ssid=ssid, reason=reason, properties=props)
        d.addCallback(add_buildset)
        def get_brs((bsid,brids)):
            brs = BuildRequestStatus(self.original.name,
                                     brids[self.original.name],
                                     self.main.main.status)
            return brs
        d.addCallback(get_brs)
        return d

    def rebuildBuild(self, bs, reason="<rebuild, no reason given>", extraProperties=None):
        if not bs.isFinished():
            return

        # Make a copy of the properties so as not to modify the original build.
        properties = Properties()
        # Don't include runtime-set properties in a rebuild request
        properties.updateFromPropertiesNoRuntime(bs.getProperties())
        if extraProperties is None:
            properties.updateFromProperties(extraProperties)

        properties_dict = dict((k,(v,s)) for (k,v,s) in properties.asList())
        ss = bs.getSourceStamp(absolute=True)
        d = ss.getSourceStampId(self.main.main)
        def add_buildset(ssid):
            return self.main.main.addBuildset(
                    builderNames=[self.original.name],
                    ssid=ssid, reason=reason, properties=properties_dict)
        d.addCallback(add_buildset)
        return d

    @defer.deferredGenerator
    def getPendingBuildRequestControls(self):
        main = self.original.main
        wfd = defer.waitForDeferred(
            main.db.buildrequests.getBuildRequests(
                buildername=self.original.name,
                claimed=False))
        yield wfd
        brdicts = wfd.getResult()

        # convert those into BuildRequest objects
        buildrequests = [ ]
        for brdict in brdicts:
            wfd = defer.waitForDeferred(
                buildrequest.BuildRequest.fromBrdict(self.main.main,
                                                     brdict))
            yield wfd
            buildrequests.append(wfd.getResult())

        # and return the corresponding control objects
        yield [ buildrequest.BuildRequestControl(self.original, r)
                 for r in buildrequests ]

    def getBuild(self, number):
        return self.original.getBuild(number)

    def ping(self):
        if not self.original.subordinates:
            self.original.builder_status.addPointEvent(["ping", "no subordinate"])
            return defer.succeed(False) # interfaces.NoSubordinateError
        dl = []
        for s in self.original.subordinates:
            dl.append(s.ping(self.original.builder_status))
        d = defer.DeferredList(dl)
        d.addCallback(self._gatherPingResults)
        return d

    def _gatherPingResults(self, res):
        for ignored,success in res:
            if not success:
                return False
        return True

