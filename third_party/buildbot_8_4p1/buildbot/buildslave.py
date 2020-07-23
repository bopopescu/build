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
# Portions Copyright Buildbot Team Members
# Portions Copyright Canonical Ltd. 2009

import time
from email.Message import Message
from email.Utils import formatdate
from zope.interface import implements
from twisted.python import log, failure
from twisted.internet import defer, reactor
from twisted.application import service
from twisted.spread import pb
from twisted.python.reflect import namedModule

from buildbot.status.subordinate import SubordinateStatus
from buildbot.status.mail import MailNotifier
from buildbot.process import metrics
from buildbot.interfaces import IBuildSubordinate, ILatentBuildSubordinate
from buildbot.process.properties import Properties
from buildbot.locks import LockAccess

class AbstractBuildSubordinate(pb.Avatar, service.MultiService):
    """This is the main-side representative for a remote buildbot subordinate.
    There is exactly one for each subordinate described in the config file (the
    c['subordinates'] list). When buildbots connect in (.attach), they get a
    reference to this instance. The BotMain object is stashed as the
    .botmain attribute. The BotMain is also our '.parent' Service.

    I represent a build subordinate -- a remote machine capable of
    running builds.  I am instantiated by the configuration file, and can be
    subclassed to add extra functionality."""

    implements(IBuildSubordinate)
    keepalive_timer = None
    keepalive_interval = None

    def __init__(self, name, password, max_builds=None,
                 notify_on_missing=[], missing_timeout=3600,
                 properties={}, locks=None, keepalive_interval=3600):
        """
        @param name: botname this machine will supply when it connects
        @param password: password this machine will supply when
                         it connects
        @param max_builds: maximum number of simultaneous builds that will
                           be run concurrently on this buildsubordinate (the
                           default is None for no limit)
        @param properties: properties that will be applied to builds run on
                           this subordinate
        @type properties: dictionary
        @param locks: A list of locks that must be acquired before this subordinate
                      can be used
        @type locks: dictionary
        """
        service.MultiService.__init__(self)
        self.subordinatename = name
        self.password = password
        self.botmain = None # no buildmain yet
        self.subordinate_status = SubordinateStatus(name)
        self.subordinate = None # a RemoteReference to the Bot, when connected
        self.subordinate_commands = None
        self.subordinatebuilders = {}
        self.max_builds = max_builds
        self.access = []
        if locks:
            self.access = locks

        self.properties = Properties()
        self.properties.update(properties, "BuildSubordinate")
        self.properties.setProperty("subordinatename", name, "BuildSubordinate")

        self.lastMessageReceived = 0
        if isinstance(notify_on_missing, str):
            notify_on_missing = [notify_on_missing]
        self.notify_on_missing = notify_on_missing
        for i in notify_on_missing:
            assert isinstance(i, str)
        self.missing_timeout = missing_timeout
        self.missing_timer = None
        self.keepalive_interval = keepalive_interval

        self._old_builder_list = None

    def identity(self):
        """
        Return a tuple describing this subordinate.  After reconfiguration a
        new subordinate with the same identity will update this one, rather
        than replacing it, thereby avoiding an interruption of current
        activity.
        """
        return (self.subordinatename, self.password, 
                '%s.%s' % (self.__class__.__module__,
                           self.__class__.__name__))

    def update(self, new):
        """
        Given a new BuildSubordinate, configure this one identically.  Because
        BuildSubordinate objects are remotely referenced, we can't replace them
        without disconnecting the subordinate, yet there's no reason to do that.
        """
        # the reconfiguration logic should guarantee this:
        assert self.subordinatename == new.subordinatename
        assert self.password == new.password
        assert self.identity() == new.identity()
        self.max_builds = new.max_builds
        self.access = new.access
        self.notify_on_missing = new.notify_on_missing
        self.missing_timeout = new.missing_timeout
        self.keepalive_interval = new.keepalive_interval

        self.properties = Properties()
        self.properties.updateFromProperties(new.properties)

        if self.botmain:
            self.updateLocks()

    def __repr__(self):
        if self.botmain:
            builders = self.botmain.getBuildersForSubordinate(self.subordinatename)
            return "<%s '%s', current builders: %s>" % \
               (self.__class__.__name__, self.subordinatename,
                ','.join(map(lambda b: b.name, builders)))
        else:
            return "<%s '%s', (no builders yet)>" % \
                (self.__class__.__name__, self.subordinatename)

    def updateLocks(self):
        # convert locks into their real form
        locks = []
        for access in self.access:
            if not isinstance(access, LockAccess):
                access = access.defaultAccess()
            lock = self.botmain.getLockByID(access.lockid)
            locks.append((lock, access))
        self.locks = [(l.getLock(self), la) for l, la in locks]

    def locksAvailable(self):
        """
        I am called to see if all the locks I depend on are available,
        in which I return True, otherwise I return False
        """
        if not self.locks:
            return True
        for lock, access in self.locks:
            if not lock.isAvailable(access):
                return False
        return True

    def acquireLocks(self):
        """
        I am called when a build is preparing to run. I try to claim all
        the locks that are needed for a build to happen. If I can't, then
        my caller should give up the build and try to get another subordinate
        to look at it.
        """
        log.msg("acquireLocks(subordinate %s, locks %s)" % (self, self.locks))
        if not self.locksAvailable():
            log.msg("subordinate %s can't lock, giving up" % (self, ))
            return False
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        return True

    def releaseLocks(self):
        """
        I am called to release any locks after a build has finished
        """
        log.msg("releaseLocks(%s): %s" % (self, self.locks))
        for lock, access in self.locks:
            lock.release(self, access)

    def setBotmain(self, botmain):
        assert not self.botmain, "BuildSubordinate already has a botmain"
        self.botmain = botmain
        self.updateLocks()
        self.startMissingTimer()

    def stopMissingTimer(self):
        if self.missing_timer:
            self.missing_timer.cancel()
            self.missing_timer = None

    def startMissingTimer(self):
        if self.notify_on_missing and self.missing_timeout and self.parent:
            self.stopMissingTimer() # in case it's already running
            self.missing_timer = reactor.callLater(self.missing_timeout,
                                                self._missing_timer_fired)

    def doKeepalive(self):
        self.keepalive_timer = reactor.callLater(self.keepalive_interval,
                                                self.doKeepalive)
        if not self.subordinate:
            return
        d = self.subordinate.callRemote("print", "Received keepalive from main")
        d.addErrback(log.msg, "Keepalive failed for '%s'" % (self.subordinatename, ))

    def stopKeepaliveTimer(self):
        if self.keepalive_timer:
            self.keepalive_timer.cancel()

    def startKeepaliveTimer(self):
        assert self.keepalive_interval
        log.msg("Starting buildsubordinate keepalive timer for '%s'" % \
                                        (self.subordinatename, ))
        self.doKeepalive()

    def recordConnectTime(self):
        if self.subordinate_status:
            self.subordinate_status.recordConnectTime()

    def isConnected(self):
        return self.subordinate

    def _missing_timer_fired(self):
        self.missing_timer = None
        # notify people, but only if we're still in the config
        if not self.parent:
            return

        buildmain = self.botmain.parent
        status = buildmain.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getTitle()
        text += ("has noticed that the buildsubordinate named %s went away\n" %
                 self.subordinatename)
        text += "\n"
        text += ("It last disconnected at %s (buildmain-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout)) # approx
        text += "\n"
        text += "The admin on record (as reported by BUILDSLAVE:info/admin)\n"
        text += "was '%s'.\n" % self.subordinate_status.getAdmin()
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getTitleURL()
        subject = "Buildbot: buildsubordinate %s was lost" % self.subordinatename
        return self._mail_missing_message(subject, text)


    def updateSubordinate(self):
        """Called to add or remove builders after the subordinate has connected.

        @return: a Deferred that indicates when an attached subordinate has
        accepted the new builders and/or released the old ones."""
        if self.subordinate:
            return self.sendBuilderList()
        else:
            return defer.succeed(None)

    def updateSubordinateStatus(self, buildStarted=None, buildFinished=None):
        if buildStarted:
            self.subordinate_status.buildStarted(buildStarted)
        if buildFinished:
            self.subordinate_status.buildFinished(buildFinished)

    @metrics.countMethod('AbstractBuildSubordinate.attached()')
    def attached(self, bot):
        """This is called when the subordinate connects.

        @return: a Deferred that fires when the attachment is complete
        """

        # the botmain should ensure this.
        assert not self.isConnected()

        metrics.MetricCountEvent.log("AbstractBuildSubordinate.attached_subordinates", 1)

        # now we go through a sequence of calls, gathering information, then
        # tell the Botmain that it can finally give this subordinate to all the
        # Builders that care about it.

        # we accumulate subordinate information in this 'state' dictionary, then
        # set it atomically if we make it far enough through the process
        state = {}

        # Reset graceful shutdown status
        self.subordinate_status.setGraceful(False)
        # We want to know when the graceful shutdown flag changes
        self.subordinate_status.addGracefulWatcher(self._gracefulChanged)

        d = defer.succeed(None)
        def _log_attachment_on_subordinate(res):
            d1 = bot.callRemote("print", "attached")
            d1.addErrback(lambda why: None)
            return d1
        d.addCallback(_log_attachment_on_subordinate)

        def _get_info(res):
            d1 = bot.callRemote("getSubordinateInfo")
            def _got_info(info):
                log.msg("Got subordinateinfo from '%s'" % self.subordinatename)
                # TODO: info{} might have other keys
                state["admin"] = info.get("admin")
                state["host"] = info.get("host")
                state["access_uri"] = info.get("access_uri", None)
                state["subordinate_environ"] = info.get("environ", {})
                state["subordinate_basedir"] = info.get("basedir", None)
                state["subordinate_system"] = info.get("system", None)
            def _info_unavailable(why):
                why.trap(pb.NoSuchMethod)
                # maybe an old subordinate, doesn't implement remote_getSubordinateInfo
                log.msg("BuildSubordinate.info_unavailable")
                log.err(why)
            d1.addCallbacks(_got_info, _info_unavailable)
            return d1
        d.addCallback(_get_info)
        self.startKeepaliveTimer()

        def _get_version(res):
            d = bot.callRemote("getVersion")
            def _got_version(version):
                state["version"] = version
            def _version_unavailable(why):
                why.trap(pb.NoSuchMethod)
                # probably an old subordinate
                state["version"] = '(unknown)'
            d.addCallbacks(_got_version, _version_unavailable)
            return d
        d.addCallback(_get_version)

        def _get_commands(res):
            d1 = bot.callRemote("getCommands")
            def _got_commands(commands):
                state["subordinate_commands"] = commands
            def _commands_unavailable(why):
                # probably an old subordinate
                log.msg("BuildSubordinate._commands_unavailable")
                if why.check(AttributeError):
                    return
                log.err(why)
            d1.addCallbacks(_got_commands, _commands_unavailable)
            return d1
        d.addCallback(_get_commands)

        def _accept_subordinate(res):
            self.subordinate_status.setAdmin(state.get("admin"))
            self.subordinate_status.setHost(state.get("host"))
            self.subordinate_status.setAccessURI(state.get("access_uri"))
            self.subordinate_status.setVersion(state.get("version"))
            self.subordinate_status.setConnected(True)
            self.subordinate_commands = state.get("subordinate_commands")
            self.subordinate_environ = state.get("subordinate_environ")
            self.subordinate_basedir = state.get("subordinate_basedir")
            self.subordinate_system = state.get("subordinate_system")
            self.subordinate = bot
            if self.subordinate_system == "win32":
                self.path_module = namedModule("win32path")
            else:
                # most eveything accepts / as separator, so posix should be a
                # reasonable fallback
                self.path_module = namedModule("posixpath")
            log.msg("bot attached")
            self.messageReceivedFromSubordinate()
            self.stopMissingTimer()
            self.botmain.parent.status.subordinateConnected(self.subordinatename)

            return self.updateSubordinate()
        d.addCallback(_accept_subordinate)
        d.addCallback(lambda _:
                self.botmain.maybeStartBuildsForSubordinate(self.subordinatename))

        # Finally, the subordinate gets a reference to this BuildSubordinate. They
        # receive this later, after we've started using them.
        d.addCallback(lambda _: self)
        return d

    def messageReceivedFromSubordinate(self):
        now = time.time()
        self.lastMessageReceived = now
        self.subordinate_status.setLastMessageReceived(now)

    def detached(self, mind):
        metrics.MetricCountEvent.log("AbstractBuildSubordinate.attached_subordinates", -1)
        self.subordinate = None
        self._old_builder_list = []
        self.subordinate_status.removeGracefulWatcher(self._gracefulChanged)
        self.subordinate_status.setConnected(False)
        log.msg("BuildSubordinate.detached(%s)" % self.subordinatename)
        self.botmain.parent.status.subordinateDisconnected(self.subordinatename)
        self.stopKeepaliveTimer()

    def disconnect(self):
        """Forcibly disconnect the subordinate.

        This severs the TCP connection and returns a Deferred that will fire
        (with None) when the connection is probably gone.

        If the subordinate is still alive, they will probably try to reconnect
        again in a moment.

        This is called in two circumstances. The first is when a subordinate is
        removed from the config file. In this case, when they try to
        reconnect, they will be rejected as an unknown subordinate. The second is
        when we wind up with two connections for the same subordinate, in which
        case we disconnect the older connection.
        """

        if not self.subordinate:
            return defer.succeed(None)
        log.msg("disconnecting old subordinate %s now" % self.subordinatename)
        # When this Deferred fires, we'll be ready to accept the new subordinate
        return self._disconnect(self.subordinate)

    def _disconnect(self, subordinate):
        # all kinds of teardown will happen as a result of
        # loseConnection(), but it happens after a reactor iteration or
        # two. Hook the actual disconnect so we can know when it is safe
        # to connect the new subordinate. We have to wait one additional
        # iteration (with callLater(0)) to make sure the *other*
        # notifyOnDisconnect handlers have had a chance to run.
        d = defer.Deferred()

        # notifyOnDisconnect runs the callback with one argument, the
        # RemoteReference being disconnected.
        def _disconnected(rref):
            reactor.callLater(0, d.callback, None)
        subordinate.notifyOnDisconnect(_disconnected)
        tport = subordinate.broker.transport
        # this is the polite way to request that a socket be closed
        tport.loseConnection()
        try:
            # but really we don't want to wait for the transmit queue to
            # drain. The remote end is unlikely to ACK the data, so we'd
            # probably have to wait for a (20-minute) TCP timeout.
            #tport._closeSocket()
            # however, doing _closeSocket (whether before or after
            # loseConnection) somehow prevents the notifyOnDisconnect
            # handlers from being run. Bummer.
            tport.offset = 0
            tport.dataBuffer = ""
        except:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")
        log.msg("waiting for subordinate to finish disconnecting")

        return d

    def sendBuilderList(self):
        our_builders = self.botmain.getBuildersForSubordinate(self.subordinatename)
        blist = [(b.name, b.subordinatebuilddir) for b in our_builders]
#        if blist == self._old_builder_list:
#            log.msg("Builder list is unchanged; not calling setBuilderList")
#            return defer.succeed(None)

        d = self.subordinate.callRemote("setBuilderList", blist)
        def sentBuilderList(ign):
            self._old_builder_list = blist
            return ign
        d.addCallback(sentBuilderList)
        return d

    def perspective_keepalive(self):
        self.messageReceivedFromSubordinate()

    def perspective_shutdown(self):
        log.msg("subordinate %s wants to shut down" % self.subordinatename)
        self.subordinate_status.setGraceful(True)

    def addSubordinateBuilder(self, sb):
        self.subordinatebuilders[sb.builder_name] = sb

    def removeSubordinateBuilder(self, sb):
        try:
            del self.subordinatebuilders[sb.builder_name]
        except KeyError:
            pass

    def buildFinished(self, sb):
        """This is called when a build on this subordinate is finished."""
        self.botmain.maybeStartBuildsForSubordinate(self.subordinatename)

    def canStartBuild(self):
        """
        I am called when a build is requested to see if this buildsubordinate
        can start a build.  This function can be used to limit overall
        concurrency on the buildsubordinate.
        """
        # If we're waiting to shutdown gracefully, then we shouldn't
        # accept any new jobs.
        if self.subordinate_status.getGraceful():
            return False

        if self.max_builds:
            active_builders = [sb for sb in self.subordinatebuilders.values()
                               if sb.isBusy()]
            if len(active_builders) >= self.max_builds:
                return False

        if not self.locksAvailable():
            return False

        return True

    def _mail_missing_message(self, subject, text):
        # first, see if we have a MailNotifier we can use. This gives us a
        # fromaddr and a relayhost.
        buildmain = self.botmain.parent
        for st in buildmain.statusTargets:
            if isinstance(st, MailNotifier):
                break
        else:
            # if not, they get a default MailNotifier, which always uses SMTP
            # to localhost and uses a dummy fromaddr of "buildbot".
            log.msg("buildsubordinate-missing msg using default MailNotifier")
            st = MailNotifier("buildbot")
        # now construct the mail

        m = Message()
        m.set_payload(text)
        m['Date'] = formatdate(localtime=True)
        m['Subject'] = subject
        m['From'] = st.fromaddr
        recipients = self.notify_on_missing
        m['To'] = ", ".join(recipients)
        d = st.sendMessage(m, recipients)
        # return the Deferred for testing purposes
        return d

    def _gracefulChanged(self, graceful):
        """This is called when our graceful shutdown setting changes"""
        self.maybeShutdown()

    @defer.deferredGenerator
    def shutdown(self):
        """Shutdown the subordinate"""
        if not self.subordinate:
            log.msg("no remote; subordinate is already shut down")
            return

        # First, try the "new" way - calling our own remote's shutdown
        # method.  The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.
        def new_way():
            d = self.subordinate.callRemote('shutdown')
            d.addCallback(lambda _ : True) # successful shutdown request
            def check_nsm(f):
                f.trap(pb.NoSuchMethod)
                return False # fall through to the old way
            d.addErrback(check_nsm)
            def check_connlost(f):
                f.trap(pb.PBConnectionLost)
                return True # the subordinate is gone, so call it finished
            d.addErrback(check_connlost)
            return d

        wfd = defer.waitForDeferred(new_way())
        yield wfd
        if wfd.getResult():
            return # done!

        # Now, the old way.  Look for a builder with a remote reference to the
        # client side subordinate.  If we can find one, then call "shutdown" on the
        # remote builder, which will cause the subordinate buildbot process to exit.
        def old_way():
            d = None
            for b in self.subordinatebuilders.values():
                if b.remote:
                    d = b.remote.callRemote("shutdown")
                    break

            if d:
                log.msg("Shutting down (old) subordinate: %s" % self.subordinatename)
                # The remote shutdown call will not complete successfully since the
                # buildbot process exits almost immediately after getting the
                # shutdown request.
                # Here we look at the reason why the remote call failed, and if
                # it's because the connection was lost, that means the subordinate
                # shutdown as expected.
                def _errback(why):
                    if why.check(pb.PBConnectionLost):
                        log.msg("Lost connection to %s" % self.subordinatename)
                    else:
                        log.err("Unexpected error when trying to shutdown %s" % self.subordinatename)
                d.addErrback(_errback)
                return d
            log.err("Couldn't find remote builder to shut down subordinate")
            return defer.succeed(None)
        wfd = defer.waitForDeferred(old_way())
        yield wfd
        wfd.getResult()

    def maybeShutdown(self):
        """Shut down this subordinate if it has been asked to shut down gracefully,
        and has no active builders."""
        if not self.subordinate_status.getGraceful():
            return
        active_builders = [sb for sb in self.subordinatebuilders.values()
                           if sb.isBusy()]
        if active_builders:
            return
        d = self.shutdown()
        d.addErrback(log.err, 'error while shutting down subordinate')

class BuildSubordinate(AbstractBuildSubordinate):

    def sendBuilderList(self):
        d = AbstractBuildSubordinate.sendBuilderList(self)
        def _sent(slist):
            # Nothing has changed, so don't need to re-attach to everything
            if not slist:
                return
            dl = []
            for name, remote in slist.items():
                # use get() since we might have changed our mind since then
                b = self.botmain.builders.get(name)
                if b:
                    d1 = b.attached(self, remote, self.subordinate_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)
        def _set_failed(why):
            log.msg("BuildSubordinate.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
        d.addCallbacks(_sent, _set_failed)
        return d

    def detached(self, mind):
        AbstractBuildSubordinate.detached(self, mind)
        self.botmain.subordinateLost(self)
        self.startMissingTimer()

    def buildFinished(self, sb):
        """This is called when a build on this subordinate is finished."""
        AbstractBuildSubordinate.buildFinished(self, sb)

        # If we're gracefully shutting down, and we have no more active
        # builders, then it's safe to disconnect
        self.maybeShutdown()

class AbstractLatentBuildSubordinate(AbstractBuildSubordinate):
    """A build subordinate that will start up a subordinate instance when needed.

    To use, subclass and implement start_instance and stop_instance.

    See ec2buildsubordinate.py for a concrete example.  Also see the stub example in
    test/test_subordinates.py.
    """

    implements(ILatentBuildSubordinate)

    substantiated = False
    substantiation_deferred = None
    substantiation_build = None
    build_wait_timer = None
    _shutdown_callback_handle = None

    def __init__(self, name, password, max_builds=None,
                 notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10,
                 properties={}, locks=None):
        AbstractBuildSubordinate.__init__(
            self, name, password, max_builds, notify_on_missing,
            missing_timeout, properties, locks)
        self.building = set()
        self.build_wait_timeout = build_wait_timeout

    def start_instance(self, build):
        # responsible for starting instance that will try to connect with this
        # main.  Should return deferred with either True (instance started)
        # or False (instance not started, so don't run a build here).  Problems
        # should use an errback.
        raise NotImplementedError

    def stop_instance(self, fast=False):
        # responsible for shutting down instance.
        raise NotImplementedError

    def substantiate(self, sb, build):
        if self.substantiated:
            self._clearBuildWaitTimer()
            self._setBuildWaitTimer()
            return defer.succeed(True)
        if self.substantiation_deferred is None:
            if self.parent and not self.missing_timer:
                # start timer.  if timer times out, fail deferred
                self.missing_timer = reactor.callLater(
                    self.missing_timeout,
                    self._substantiation_failed, defer.TimeoutError())
            self.substantiation_deferred = defer.Deferred()
            self.substantiation_build = build
            if self.subordinate is None:
                d = self._substantiate(build) # start up instance
                d.addErrback(log.err, "while substantiating")
            # else: we're waiting for an old one to detach.  the _substantiate
            # will be done in ``detached`` below.
        return self.substantiation_deferred

    def _substantiate(self, build):
        # register event trigger
        d = self.start_instance(build)
        self._shutdown_callback_handle = reactor.addSystemEventTrigger(
            'before', 'shutdown', self._soft_disconnect, fast=True)
        def start_instance_result(result):
            # If we don't report success, then preparation failed.
            if not result:
                log.msg("Subordinate '%s' doesn not want to substantiate at this time" % (self.subordinatename,))
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                d.callback(False)
            return result
        def clean_up(failure):
            if self.missing_timer is not None:
                self.missing_timer.cancel()
                self._substantiation_failed(failure)
            if self._shutdown_callback_handle is not None:
                handle = self._shutdown_callback_handle
                del self._shutdown_callback_handle
                reactor.removeSystemEventTrigger(handle)
            return failure
        d.addCallbacks(start_instance_result, clean_up)
        return d

    def attached(self, bot):
        if self.substantiation_deferred is None:
            msg = 'Subordinate %s received connection while not trying to ' \
                    'substantiate.  Disconnecting.' % (self.subordinatename,)
            log.msg(msg)
            self._disconnect(bot)
            return defer.fail(RuntimeError(msg))
        return AbstractBuildSubordinate.attached(self, bot)

    def detached(self, mind):
        AbstractBuildSubordinate.detached(self, mind)
        if self.substantiation_deferred is not None:
            d = self._substantiate(self.substantiation_build)
            d.addErrback(log.err, 'while re-substantiating')

    def _substantiation_failed(self, failure):
        self.missing_timer = None
        if self.substantiation_deferred:
            d = self.substantiation_deferred
            self.substantiation_deferred = None
            self.substantiation_build = None
            d.errback(failure)
        self.insubstantiate()
        # notify people, but only if we're still in the config
        if not self.parent or not self.notify_on_missing:
            return

        buildmain = self.botmain.parent
        status = buildmain.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getTitle()
        text += ("has noticed that the latent buildsubordinate named %s \n" %
                 self.subordinatename)
        text += "never substantiated after a request\n"
        text += "\n"
        text += ("The request was made at %s (buildmain-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout)) # approx
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getTitleURL()
        subject = "Buildbot: buildsubordinate %s never substantiated" % self.subordinatename
        return self._mail_missing_message(subject, text)

    def buildStarted(self, sb):
        assert self.substantiated
        self._clearBuildWaitTimer()
        self.building.add(sb.builder_name)

    def buildFinished(self, sb):
        AbstractBuildSubordinate.buildFinished(self, sb)

        self.building.remove(sb.builder_name)
        if not self.building:
            self._setBuildWaitTimer()

    def _clearBuildWaitTimer(self):
        if self.build_wait_timer is not None:
            if self.build_wait_timer.active():
                self.build_wait_timer.cancel()
            self.build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        self.build_wait_timer = reactor.callLater(
            self.build_wait_timeout, self._soft_disconnect)

    def insubstantiate(self, fast=False):
        self._clearBuildWaitTimer()
        d = self.stop_instance(fast)
        if self._shutdown_callback_handle is not None:
            handle = self._shutdown_callback_handle
            del self._shutdown_callback_handle
            reactor.removeSystemEventTrigger(handle)
        self.substantiated = False
        self.building.clear() # just to be sure
        return d

    def _soft_disconnect(self, fast=False):
        d = AbstractBuildSubordinate.disconnect(self)
        if self.subordinate is not None:
            # this could be called when the subordinate needs to shut down, such as
            # in BotMain.removeSubordinate, *or* when a new subordinate requests a
            # connection when we already have a subordinate. It's not clear what to
            # do in the second case: this shouldn't happen, and if it
            # does...if it's a latent subordinate, shutting down will probably kill
            # something we want...but we can't know what the status is. So,
            # here, we just do what should be appropriate for the first case,
            # and put our heads in the sand for the second, at least for now.
            # The best solution to the odd situation is removing it as a
            # possibilty: make the main in charge of connecting to the
            # subordinate, rather than vice versa. TODO.
            d = defer.DeferredList([d, self.insubstantiate(fast)])
        else:
            if self.substantiation_deferred is not None:
                # unlike the previous block, we don't expect this situation when
                # ``attached`` calls ``disconnect``, only when we get a simple
                # request to "go away".
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                self.substantiation_build = None
                d.errback(failure.Failure(
                    RuntimeError("soft disconnect aborted substantiation")))
                if self.missing_timer:
                    self.missing_timer.cancel()
                    self.missing_timer = None
                self.stop_instance()
        return d

    def disconnect(self):
        # This returns a Deferred but we don't use it
        self._soft_disconnect() 
        # this removes the subordinate from all builders.  It won't come back
        # without a restart (or maybe a sighup)
        self.botmain.subordinateLost(self)

    def stopService(self):
        res = defer.maybeDeferred(AbstractBuildSubordinate.stopService, self)
        if self.subordinate is not None:
            d = self._soft_disconnect()
            res = defer.DeferredList([res, d])
        return res

    def updateSubordinate(self):
        """Called to add or remove builders after the subordinate has connected.

        Also called after botmain's builders are initially set.

        @return: a Deferred that indicates when an attached subordinate has
        accepted the new builders and/or released the old ones."""
        for b in self.botmain.getBuildersForSubordinate(self.subordinatename):
            if b.name not in self.subordinatebuilders:
                b.addLatentSubordinate(self)
        return AbstractBuildSubordinate.updateSubordinate(self)

    def sendBuilderList(self):
        d = AbstractBuildSubordinate.sendBuilderList(self)
        def _sent(slist):
            if not slist:
                return
            dl = []
            for name, remote in slist.items():
                # use get() since we might have changed our mind since then.
                # we're checking on the builder in addition to the
                # subordinatebuilders out of a bit of paranoia.
                b = self.botmain.builders.get(name)
                sb = self.subordinatebuilders.get(name)
                if b and sb:
                    d1 = sb.attached(self, remote, self.subordinate_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)
        def _set_failed(why):
            log.msg("BuildSubordinate.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
            if self.substantiation_deferred:
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                self.substantiation_build = None
                d.errback(why)
            if self.missing_timer:
                self.missing_timer.cancel()
                self.missing_timer = None
            # TODO: maybe log?  send an email?
            return why
        d.addCallbacks(_sent, _set_failed)
        def _substantiated(res):
            log.msg("Subordinate %s substantiated \o/" % self.subordinatename)
            self.substantiated = True
            if not self.substantiation_deferred:
                log.msg("No substantiation deferred for %s" % self.subordinatename)
            if self.substantiation_deferred:
                log.msg("Firing %s substantiation deferred with success" % self.subordinatename)
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                self.substantiation_build = None
                d.callback(True)
            # note that the missing_timer is already handled within
            # ``attached``
            if not self.building:
                self._setBuildWaitTimer()
        d.addCallback(_substantiated)
        return d
