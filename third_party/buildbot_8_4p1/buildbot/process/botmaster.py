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


from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.application import service

from buildbot.process.builder import Builder
from buildbot import interfaces, locks
from buildbot.process import metrics

class BotMain(service.MultiService):

    """This is the main-side service which manages remote buildbot subordinates.
    It provides them with BuildSubordinates, and distributes build requests to
    them."""

    debug = 0
    reactor = reactor

    def __init__(self, main):
        service.MultiService.__init__(self)
        self.main = main

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the main-side object that defines and controls a build.

        # self.subordinates contains a ready BuildSubordinate instance for each
        # potential buildsubordinate, i.e. all the ones listed in the config file.
        # If the subordinate is connected, self.subordinates[subordinatename].subordinate will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.subordinates = {} # maps subordinatename to BuildSubordinate
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        # self.prioritizeBuilders is the callable override for builder order
        # traversal
        self.prioritizeBuilders = None

        self.shuttingDown = False

        self.lastSubordinatePortnum = None

        # subscription to new build requests
        self.buildrequest_sub = None

        # a distributor for incoming build requests; see below
        self.brd = BuildRequestDistributor(self)
        self.brd.setServiceParent(self)

    def cleanShutdown(self, _reactor=reactor):
        """Shut down the entire process, once all currently-running builds are
        complete."""
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True

        # first, stop the distributor; this will finish any ongoing scheduling
        # operations before firing
        d = self.brd.stopService()

        # then wait for all builds to finish
        def wait(_):
            l = []
            for builder in self.builders.values():
                for build in builder.builder_status.getCurrentBuilds():
                    l.append(build.waitUntilFinished())
            if len(l) == 0:
                log.msg("No running jobs, starting shutdown immediately")
            else:
                log.msg("Waiting for %i build(s) to finish" % len(l))
                return defer.DeferredList(l)
        d.addCallback(wait)

        # Finally, shut the whole process down
        def shutdown(ign):
            # Double check that we're still supposed to be shutting down
            # The shutdown may have been cancelled!
            if self.shuttingDown:
                # Check that there really aren't any running builds
                for builder in self.builders.values():
                    n = len(builder.builder_status.getCurrentBuilds())
                    if n > 0:
                        log.msg("Not shutting down, builder %s has %i builds running" % (builder, n))
                        log.msg("Trying shutdown sequence again")
                        self.shuttingDown = False
                        self.cleanShutdown()
                        return
                log.msg("Stopping reactor")
                _reactor.stop()
            else:
                self.brd.startService()
        d.addCallback(shutdown)
        d.addErrback(log.err, 'while processing cleanShutdown')

    def cancelCleanShutdown(self):
        """Cancel a clean shutdown that is already in progress, if any"""
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    def loadConfig_Subordinates(self, new_subordinates):
        timer = metrics.Timer("BotMain.loadConfig_Subordinates()")
        timer.start()
        new_portnum = (self.lastSubordinatePortnum is not None
                   and self.lastSubordinatePortnum != self.main.subordinatePortnum)
        if new_portnum:
            # it turns out this is pretty hard..
            raise ValueError("changing subordinatePortnum in reconfig is not supported")
        self.lastSubordinatePortnum = self.main.subordinatePortnum

        old_subordinates = [c for c in list(self)
                      if interfaces.IBuildSubordinate.providedBy(c)]

        # identify added/removed subordinates. For each subordinate we construct a tuple
        # of (name, password, class), and we consider the subordinate to be already
        # present if the tuples match. (we include the class to make sure
        # that BuildSubordinate(name,pw) is different than
        # SubclassOfBuildSubordinate(name,pw) ). If the password or class has
        # changed, we will remove the old version of the subordinate and replace it
        # with a new one. If anything else has changed, we just update the
        # old BuildSubordinate instance in place. If the name has changed, of
        # course, it looks exactly the same as deleting one subordinate and adding
        # an unrelated one.

        old_t = {}
        for s in old_subordinates:
            old_t[s.identity()] = s
        new_t = {}
        for s in new_subordinates:
            new_t[s.identity()] = s
        removed = [old_t[t]
                   for t in old_t
                   if t not in new_t]
        added = [new_t[t]
                 for t in new_t
                 if t not in old_t]
        remaining_t = [t
                       for t in new_t
                       if t in old_t]

        # removeSubordinate will hang up on the old bot
        dl = []
        for s in removed:
            dl.append(self.removeSubordinate(s))
        d = defer.DeferredList(dl, fireOnOneErrback=True)

        def add_new(res):
            for s in added:
                self.addSubordinate(s)
        d.addCallback(add_new)

        def update_remaining(_):
            for t in remaining_t:
                old_t[t].update(new_t[t])

        d.addCallback(update_remaining)

        def stop(_):
            metrics.MetricCountEvent.log("num_subordinates",
                len(self.subordinates), absolute=True)
            timer.stop()
            return _
        d.addBoth(stop)

        return d

    def addSubordinate(self, s):
        s.setServiceParent(self)
        s.setBotmain(self)
        self.subordinates[s.subordinatename] = s
        s.pb_registration = self.main.pbmanager.register(
                self.main.subordinatePortnum, s.subordinatename,
                s.password, self.getPerspective)
        # do not call maybeStartBuildsForSubordinate here, as the subordinate has not
        # necessarily attached yet

    @metrics.countMethod('BotMain.removeSubordinate()')
    def removeSubordinate(self, s):
        d = s.disownServiceParent()
        d.addCallback(lambda _ : s.pb_registration.unregister())
        d.addCallback(lambda _ : self.subordinates[s.subordinatename].disconnect())
        def delsubordinate(_):
            del self.subordinates[s.subordinatename]
        d.addCallback(delsubordinate)
        return d

    @metrics.countMethod('BotMain.subordinateLost()')
    def subordinateLost(self, bot):
        metrics.MetricCountEvent.log("BotMain.attached_subordinates", -1)
        for name, b in self.builders.items():
            if bot.subordinatename in b.subordinatenames:
                b.detached(bot)

    @metrics.countMethod('BotMain.getBuildersForSubordinate()')
    def getBuildersForSubordinate(self, subordinatename):
        return [b
                for b in self.builders.values()
                if subordinatename in b.subordinatenames]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        allBuilders = [self.builders[name] for name in self.builderNames]
        return allBuilders

    def setBuilders(self, builders):
        # TODO: diff against previous list of builders instead of replacing
        # wholesale?
        self.builders = {}
        self.builderNames = []
        d = defer.DeferredList([b.disownServiceParent() for b in list(self)
                                if isinstance(b, Builder)],
                               fireOnOneErrback=True)
        def _add(ign):
            log.msg("setBuilders._add: %s %s" % (list(self), [b.name for b in builders]))
            for b in builders:
                for subordinatename in b.subordinatenames:
                    # this is actually validated earlier
                    assert subordinatename in self.subordinates
                self.builders[b.name] = b
                self.builderNames.append(b.name)
                b.setBotmain(self)
                b.setServiceParent(self)
        d.addCallback(_add)
        d.addCallback(lambda ign: self._updateAllSubordinates())
        # N.B. this takes care of starting all builders at main startup
        d.addCallback(lambda _ :
            self.maybeStartBuildsForAllBuilders())
        return d

    def _updateAllSubordinates(self):
        """Notify all buildsubordinates about changes in their Builders."""
        timer = metrics.Timer("BotMain._updateAllSubordinates()")
        timer.start()
        dl = []
        for s in self.subordinates.values():
            d = s.updateSubordinate()
            d.addErrback(log.err)
            dl.append(d)
        d = defer.DeferredList(dl)
        def stop(_):
            timer.stop()
            return _
        d.addBoth(stop)
        return d

    @metrics.countMethod('BotMain.shouldMergeRequests()')
    def shouldMergeRequests(self, builder, req1, req2):
        """Determine whether two BuildRequests should be merged for
        the given builder.

        """
        if self.mergeRequests is not None:
            if callable(self.mergeRequests):
                return self.mergeRequests(builder, req1, req2)
            elif self.mergeRequests == False:
                # To save typing, this allows c['mergeRequests'] = False
                return False
        return req1.canBeMergedWith(req2)

    def getPerspective(self, mind, subordinatename):
        sl = self.subordinates[subordinatename]
        if not sl:
            return None
        metrics.MetricCountEvent.log("BotMain.attached_subordinates", 1)

        # record when this connection attempt occurred
        sl.recordConnectTime()

        if sl.isConnected():
            # duplicate subordinate - send it to arbitration
            arb = DuplicateSubordinateArbitrator(sl)
            return arb.getPerspective(mind, subordinatename)
        else:
            log.msg("subordinate '%s' attaching from %s" % (subordinatename, mind.broker.transport.getPeer()))
            return sl

    def startService(self):
        def buildRequestAdded(notif):
            log.msg("Processing new build request: %s" % notif)
            self.maybeStartBuildsForBuilder(notif['buildername'])
        self.buildrequest_sub = \
            self.main.subscribeToBuildRequests(buildRequestAdded)
        service.MultiService.startService(self)

    def stopService(self):
        if self.buildrequest_sub:
            self.buildrequest_sub.unsubscribe()
            self.buildrequest_sub = None
        for b in self.builders.values():
            b.builder_status.addPointEvent(["main", "shutdown"])
            b.builder_status.saveYourself()
        return service.MultiService.stopService(self)

    def getLockByID(self, lockid):
        """Convert a Lock identifier into an actual Lock instance.
        @param lockid: a locks.MainLock or locks.SubordinateLock instance
        @return: a locks.RealMainLock or locks.RealSubordinateLock instance
        """
        assert isinstance(lockid, (locks.MainLock, locks.SubordinateLock))
        if not lockid in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the main.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MainLock and SubordinateLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def maybeStartBuildsForBuilder(self, buildername):
        """
        Call this when something suggests that a particular builder may now
        be available to start a build.

        @param buildername: the name of the builder
        """
        self.brd.maybeStartBuildsOn([buildername])

    def maybeStartBuildsForSubordinate(self, subordinate_name):
        """
        Call this when something suggests that a particular subordinate may now be
        available to start a build.

        @param subordinate_name: the name of the subordinate
        """
        builders = self.getBuildersForSubordinate(subordinate_name)
        self.brd.maybeStartBuildsOn([ b.name for b in builders ])

    def maybeStartBuildsForAllBuilders(self):
        """
        Call this when something suggests that this would be a good time to start some
        builds, but nothing more specific.
        """
        self.brd.maybeStartBuildsOn(self.builderNames)

class BuildRequestDistributor(service.Service):
    """
    Special-purpose class to handle distributing build requests to builders by
    calling their C{maybeStartBuild} method.

    This takes account of the C{prioritizeBuilders} configuration, and is
    highly re-entrant; that is, if a new build request arrives while builders
    are still working on the previous build request, then this class will
    correctly re-prioritize invocations of builders' C{maybeStartBuild}
    methods.
    """

    def __init__(self, botmain):
        self.botmain = botmain
        self.main = botmain.main

        # lock to ensure builders are only sorted once at any time
        self.pending_builders_lock = defer.DeferredLock()

        # sorted list of names of builders that need their maybeStartBuild
        # method invoked.
        self._pending_builders = []
        self.activity_lock = defer.DeferredLock()
        self.active = False

    def stopService(self):
        # let the parent stopService succeed between activity; then the loop
        # will stop calling itself, since self.running is false
        d = self.activity_lock.acquire()
        d.addCallback(lambda _ : service.Service.stopService(self))
        d.addBoth(lambda _ : self.activity_lock.release())
        return d

    @defer.deferredGenerator
    def maybeStartBuildsOn(self, new_builders):
        """
        Try to start any builds that can be started right now.  This function
        returns immediately, and promises to trigger those builders
        eventually.

        @param new_builders: names of new builders that should be given the
        opportunity to check for new requests.
        """
        new_builders = set(new_builders)
        existing_pending = set(self._pending_builders)

        # if we won't add any builders, there's nothing to do
        if new_builders < existing_pending:
            return

        # reset the list of pending builders; this is async, so begin
        # by grabbing a lock
        wfd = defer.waitForDeferred(
            self.pending_builders_lock.acquire())
        yield wfd
        wfd.getResult()

        try:
            # re-fetch existing_pending, in case it has changed while acquiring
            # the lock
            existing_pending = set(self._pending_builders)

            # then sort the new, expanded set of builders
            wfd = defer.waitForDeferred(
                self._sortBuilders(list(existing_pending | new_builders)))
            yield wfd
            self._pending_builders = wfd.getResult()

            # start the activity loop, if we aren't already working on that.
            if not self.active:
                self._activityLoop()
        except:
            log.err(Failure(),
                    "while attempting to start builds on %s" % self.name)

        # release the lock unconditionally
        self.pending_builders_lock.release()

    @defer.deferredGenerator
    def _defaultSorter(self, main, builders):
        timer = metrics.Timer("BuildRequestDistributor._defaultSorter()")
        timer.start()
        # perform an asynchronous schwarzian transform, transforming None
        # into sys.maxint so that it sorts to the end
        def xform(bldr):
            d = defer.maybeDeferred(lambda :
                    bldr.getOldestRequestTime())
            d.addCallback(lambda time :
                (((time is None) and None or time),bldr))
            return d
        wfd = defer.waitForDeferred(
            defer.gatherResults(
                [ xform(bldr) for bldr in builders ]))
        yield wfd
        xformed = wfd.getResult()

        # sort the transformed list synchronously, comparing None to the end of
        # the list
        def nonecmp(a,b):
            if a[0] is None: return 1
            if b[0] is None: return -1
            return cmp(a,b)
        xformed.sort(cmp=nonecmp)

        # and reverse the transform
        yield [ xf[1] for xf in xformed ]
        timer.stop()

    @defer.deferredGenerator
    def _sortBuilders(self, buildernames):
        timer = metrics.Timer("BuildRequestDistributor._sortBuilders()")
        timer.start()
        # note that this takes and returns a list of builder names

        # convert builder names to builders
        builders_dict = self.botmain.builders
        builders = [ builders_dict.get(n)
                     for n in buildernames
                     if n in builders_dict ]

        # find a sorting function
        sorter = self.botmain.prioritizeBuilders
        if not sorter:
            sorter = self._defaultSorter

        # run it
        try:
            wfd = defer.waitForDeferred(
                defer.maybeDeferred(lambda :
                    sorter(self.main, builders)))
            yield wfd
            builders = wfd.getResult()
        except:
            log.msg("Exception prioritizing builders; order unspecified")
            log.err(Failure())

        # and return the names
        yield [ b.name for b in builders ]
        timer.stop()

    @defer.deferredGenerator
    def _activityLoop(self):
        self.active = True

        timer = metrics.Timer('BuildRequestDistributor._activityLoop()')
        timer.start()

        while 1:
            wfd = defer.waitForDeferred(
                self.activity_lock.acquire())
            yield wfd
            wfd.getResult()

            # lock pending_builders, pop an element from it, and release
            wfd = defer.waitForDeferred(
                self.pending_builders_lock.acquire())
            yield wfd
            wfd.getResult()

            # bail out if we shouldn't keep looping
            if not self.running or not self._pending_builders:
                self.pending_builders_lock.release()
                self.activity_lock.release()
                break

            bldr_name = self._pending_builders.pop(0)
            self.pending_builders_lock.release()

            try:
                wfd = defer.waitForDeferred(
                    self._callABuilder(bldr_name))
                yield wfd
                wfd.getResult()
            except:
                log.err(Failure(),
                        "from maybeStartBuild for builder '%s'" % (bldr_name,))

            self.activity_lock.release()

        timer.stop()

        self.active = False
        self._quiet()

    def _callABuilder(self, bldr_name):
        # get the actual builder object
        bldr = self.botmain.builders.get(bldr_name)
        if not bldr:
            return defer.succeed(None)

        d = bldr.maybeStartBuild()
        d.addErrback(log.err, 'in maybeStartBuild for %r' % (bldr,))
        return d

    def _quiet(self):
        # shim for tests
        pass # pragma: no cover


class DuplicateSubordinateArbitrator(object):
    """Utility class to arbitrate the situation when a new subordinate connects with
    the name of an existing, connected subordinate"""
    # There are several likely duplicate subordinate scenarios in practice:
    #
    # 1. two subordinates are configured with the same username/password
    #
    # 2. the same subordinate process believes it is disconnected (due to a network
    # hiccup), and is trying to reconnect
    #
    # For the first case, we want to prevent the two subordinates from repeatedly
    # superseding one another (which results in lots of failed builds), so we
    # will prefer the old subordinate.  However, for the second case we need to
    # detect situations where the old subordinate is "gone".  Sometimes "gone" means
    # that the TCP/IP connection to it is in a long timeout period (10-20m,
    # depending on the OS configuration), so this can take a while.

    PING_TIMEOUT = 10
    """Timeout for pinging the old subordinate.  Set this to something quite long, as
    a very busy subordinate (e.g., one sending a big log chunk) may take a while to
    return a ping.

    @ivar old_subordinate: L{buildbot.process.subordinatebuilder.AbstractSubordinateBuilder}
    instance
    """

    def __init__(self, subordinate):
        self.old_subordinate = subordinate

    def getPerspective(self, mind, subordinatename):
        self.new_subordinate_mind = mind

        old_tport = self.old_subordinate.subordinate.broker.transport
        new_tport = mind.broker.transport
        log.msg("duplicate subordinate %s; delaying new subordinate (%s) and pinging old (%s)" % 
                (self.old_subordinate.subordinatename, new_tport.getPeer(), old_tport.getPeer()))

        # delay the new subordinate until we decide what to do with it
        self.new_subordinate_d = defer.Deferred()

        # Ping the old subordinate.  If this kills it, then we can allow the new
        # subordinate to connect.  If this does not kill it, then we disconnect
        # the new subordinate.
        self.ping_old_subordinate_done = False
        self.ping_new_subordinate_done = False
        self.old_subordinate_connected = True
        self.ping_old_subordinate(new_tport.getPeer())

        # Print a message on the new subordinate, if possible.
        self.ping_new_subordinate()

        return self.new_subordinate_d

    def ping_new_subordinate(self):
        d = self.new_subordinate_mind.callRemote("print",
            "main already has a connection named '%s' - checking its liveness"
                        % self.old_subordinate.subordinatename)
        def done(_):
            # failure or success, doesn't matter
            self.ping_new_subordinate_done = True
            self.maybe_done()
        d.addBoth(done)

    def ping_old_subordinate(self, new_peer):
        # set a timer on this ping, in case the network is bad.  TODO: a timeout
        # on the ping itself is not quite what we want.  If there is other data
        # flowing over the PB connection, then we should keep waiting.  Bug #1703
        def timeout():
            self.ping_old_subordinate_timeout = None
            self.ping_old_subordinate_timed_out = True
            self.old_subordinate_connected = False
            self.ping_old_subordinate_done = True
            self.maybe_done()
        self.ping_old_subordinate_timeout = reactor.callLater(self.PING_TIMEOUT, timeout)
        self.ping_old_subordinate_timed_out = False

        try:
          d = self.old_subordinate.subordinate.callRemote(
              "print",
              "main got a duplicate connection from %s; keeping this one"
              % new_peer)
        except pb.DeadReferenceError():
          timeout()
          return

        def clear_timeout(r):
            if self.ping_old_subordinate_timeout:
                self.ping_old_subordinate_timeout.cancel()
                self.ping_old_subordinate_timeout = None
            return r
        d.addBoth(clear_timeout)

        def old_gone(f):
            if self.ping_old_subordinate_timed_out:
                return # ignore after timeout
            f.trap(pb.PBConnectionLost)
            log.msg(("connection lost while pinging old subordinate '%s' - " +
                     "keeping new subordinate") % self.old_subordinate.subordinatename)
            self.old_subordinate_connected = False
        d.addErrback(old_gone)

        def other_err(f):
            if self.ping_old_subordinate_timed_out:
                return # ignore after timeout
            log.msg("unexpected error while pinging old subordinate; disconnecting it")
            log.err(f)
            self.old_subordinate_connected = False
        d.addErrback(other_err)

        def done(_):
            if self.ping_old_subordinate_timed_out:
                return # ignore after timeout
            self.ping_old_subordinate_done = True
            self.maybe_done()
        d.addCallback(done)

    def maybe_done(self):
        if not self.ping_new_subordinate_done or not self.ping_old_subordinate_done:
            return

        # both pings are done, so sort out the results
        if self.old_subordinate_connected:
            self.disconnect_new_subordinate()
        else:
            self.start_new_subordinate()

    def start_new_subordinate(self, count=20):
        if not self.new_subordinate_d:
            return

        # we need to wait until the old subordinate has actually disconnected, which
        # can take a little while -- but don't wait forever!
        if self.old_subordinate.isConnected():
            if self.old_subordinate.subordinate:
                self.old_subordinate.subordinate.broker.transport.loseConnection()
            if count < 0:
                log.msg("WEIRD: want to start new subordinate, but the old subordinate will not disconnect")
                self.disconnect_new_subordinate()
            else:
                reactor.callLater(0.1, self.start_new_subordinate, count-1)
            return

        d = self.new_subordinate_d
        self.new_subordinate_d = None
        d.callback(self.old_subordinate)

    def disconnect_new_subordinate(self):
        if not self.new_subordinate_d:
            return
        d = self.new_subordinate_d
        self.new_subordinate_d = None
        log.msg("rejecting duplicate subordinate with exception")
        d.errback(Failure(RuntimeError("rejecting duplicate subordinate")))


