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

import os
import shutil
import socket

from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import reactor, defer
from twisted.cred import checkers, portal
from zope.interface import implements

from buildsubordinate import bot

from mock import Mock

# I don't see any simple way to test the PB equipment without actually setting
# up a TCP connection.  This just tests that the PB code will connect and can
# execute a basic ping.  The rest is done without TCP (or PB) in other test modules.

class MainPerspective(pb.Avatar):
    def __init__(self, on_keepalive=None):
        self.on_keepalive = on_keepalive

    def perspective_keepalive(self):
        if self.on_keepalive:
            on_keepalive, self.on_keepalive = self.on_keepalive, None
            on_keepalive()

class MainRealm:
    def __init__(self, perspective, on_attachment):
        self.perspective = perspective
        self.on_attachment = on_attachment

    implements(portal.IRealm)
    def requestAvatar(self, avatarId, mind, *interfaces):
        assert pb.IPerspective in interfaces
        self.mind = mind
        self.perspective.mind = mind
        d = defer.succeed(None)
        if self.on_attachment:
            d.addCallback(lambda _: self.on_attachment(mind))
        def returnAvatar(_):
            return pb.IPerspective, self.perspective, lambda: None
        d.addCallback(returnAvatar)
        return d

    def shutdown(self):
        return self.mind.broker.transport.loseConnection()

class TestBuildSubordinate(unittest.TestCase):

    def setUp(self):
        self.realm = None
        self.buildsubordinate = None
        self.listeningport = None

        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        # the subordinate tries to call socket.getfqdn to write its hostname; this hangs
        # without network, so fake it
        self.patch(socket, "getfqdn", lambda : 'test-hostname.domain.com')

    def tearDown(self):
        d = defer.succeed(None)
        if self.realm:
            d.addCallback(lambda _ : self.realm.shutdown())
        if self.buildsubordinate and self.buildsubordinate.running:
            d.addCallback(lambda _ : self.buildsubordinate.stopService())
        if self.listeningport:
            d.addCallback(lambda _ : self.listeningport.stopListening())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def start_main(self, perspective, on_attachment=None):
        self.realm = MainRealm(perspective, on_attachment)
        p = portal.Portal(self.realm)
        p.registerChecker(
            checkers.InMemoryUsernamePasswordDatabaseDontUse(testy="westy"))
        self.listeningport = reactor.listenTCP(0, pb.PBServerFactory(p), interface='127.0.0.1')
        # return the dynamically allocated port number
        return self.listeningport.getHost().port

    def test_constructor_minimal(self):
        # only required arguments
        bot.BuildSubordinate('mstr', 9010, 'me', 'pwd', '/s', 10, False)

    def test_constructor_083_tac(self):
        # invocation as made from default 083 tac files
        bot.BuildSubordinate('mstr', 9010, 'me', 'pwd', '/s', 10, False,
                umask=0123, maxdelay=10)

    def test_constructor_full(self):
        # invocation with all args
        bot.BuildSubordinate('mstr', 9010, 'me', 'pwd', '/s', 10, False,
                umask=0123, maxdelay=10, keepaliveTimeout=10,
                unicode_encoding='utf8', allow_shutdown=True)

    def test_buildsubordinate_print(self):
        d = defer.Deferred()

        # set up to call print when we are attached, and chain the results onto
        # the deferred for the whole test
        def call_print(mind):
            print_d = mind.callRemote("print", "Hi, subordinate.")
            print_d.addCallbacks(d.callback, d.errback)

        # start up the main and subordinate
        persp = MainPerspective()
        port = self.start_main(persp, on_attachment=call_print)
        self.buildsubordinate = bot.BuildSubordinate("127.0.0.1", port,
                "testy", "westy", self.basedir,
                keepalive=0, usePTY=False, umask=022)
        self.buildsubordinate.startService()

        # and wait for the result of the print
        return d

    def test_recordHostname(self):
        self.buildsubordinate = bot.BuildSubordinate("127.0.0.1", 9999,
                "testy", "westy", self.basedir,
                keepalive=0, usePTY=False, umask=022)
        self.buildsubordinate.recordHostname(self.basedir)
        self.assertEqual(open(os.path.join(self.basedir, "twistd.hostname")).read().strip(),
                         'test-hostname.domain.com')

    def test_buildsubordinate_graceful_shutdown(self):
        """Test that running the build subordinate's gracefulShutdown method results
        in a call to the main's shutdown method"""
        d = defer.Deferred()

        fakepersp = Mock()
        called = []
        def fakeCallRemote(*args):
            called.append(args)
            d1 = defer.succeed(None)
            return d1
        fakepersp.callRemote = fakeCallRemote

        # set up to call shutdown when we are attached, and chain the results onto
        # the deferred for the whole test
        def call_shutdown(mind):
            self.buildsubordinate.bf.perspective = fakepersp
            shutdown_d = self.buildsubordinate.gracefulShutdown()
            shutdown_d.addCallbacks(d.callback, d.errback)

        persp = MainPerspective()
        port = self.start_main(persp, on_attachment=call_shutdown)

        self.buildsubordinate = bot.BuildSubordinate("127.0.0.1", port,
                "testy", "westy", self.basedir,
                keepalive=0, usePTY=False, umask=022)

        self.buildsubordinate.startService()

        def check(ign):
            self.assertEquals(called, [('shutdown',)])
        d.addCallback(check)

        return d

    def test_buildsubordinate_shutdown(self):
        """Test watching an existing shutdown_file results in gracefulShutdown
        being called."""

        buildsubordinate = bot.BuildSubordinate("127.0.0.1", 1234,
                "testy", "westy", self.basedir,
                keepalive=0, usePTY=False, umask=022,
                allow_shutdown='file')

        # Mock out gracefulShutdown
        buildsubordinate.gracefulShutdown = Mock()

        # Mock out os.path methods
        exists = Mock()
        mtime = Mock()

        self.patch(os.path, 'exists', exists)
        self.patch(os.path, 'getmtime', mtime)

        # Pretend that the shutdown file doesn't exist
        mtime.return_value = 0
        exists.return_value = False

        buildsubordinate._checkShutdownFile()

        # We shouldn't have called gracefulShutdown
        self.assertEquals(buildsubordinate.gracefulShutdown.call_count, 0)

        # Pretend that the file exists now, with an mtime of 2
        exists.return_value = True
        mtime.return_value = 2
        buildsubordinate._checkShutdownFile()

        # Now we should have changed gracefulShutdown
        self.assertEquals(buildsubordinate.gracefulShutdown.call_count, 1)

        # Bump the mtime again, and make sure we call shutdown again
        mtime.return_value = 3
        buildsubordinate._checkShutdownFile()
        self.assertEquals(buildsubordinate.gracefulShutdown.call_count, 2)

        # Try again, we shouldn't call shutdown another time
        buildsubordinate._checkShutdownFile()
        self.assertEquals(buildsubordinate.gracefulShutdown.call_count, 2)
