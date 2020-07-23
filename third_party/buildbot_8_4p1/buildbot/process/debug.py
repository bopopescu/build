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
from buildbot.pbutil import NewCredPerspective
from buildbot import interfaces
from buildbot.process.properties import Properties

class DebugPerspective(NewCredPerspective):
    def attached(self, mind):
        return self
    def detached(self, mind):
        pass

    def perspective_requestBuild(self, buildername, reason, branch, revision, properties={}):
        from buildbot.sourcestamp import SourceStamp
        c = interfaces.IControl(self.main)
        bc = c.getBuilder(buildername)
        ss = SourceStamp(branch, revision)
        bpr = Properties()
        bpr.update(properties, "remote requestBuild")
        return bc.submitBuildRequest(ss, reason, bpr)

    def perspective_pingBuilder(self, buildername):
        c = interfaces.IControl(self.main)
        bc = c.getBuilder(buildername)
        bc.ping()

    def perspective_reload(self):
        log.msg("doing reload of the config file")
        self.main.loadTheConfigFile()

    def perspective_pokeIRC(self):
        log.msg("saying something on IRC")
        from buildbot.status import words
        for s in self.main:
            if isinstance(s, words.IRC):
                bot = s.f
                for channel in bot.channels:
                    print " channel", channel
                    bot.p.msg(channel, "Ow, quit it")

    def perspective_print(self, msg):
        log.msg("debug %s" % msg)

def registerDebugClient(main, subordinatePortnum, debugPassword, pbmanager):
    def perspFactory(main, mind, username):
        persp = DebugPerspective()
        persp.main = main
        persp.botmain = main
        return persp
    return pbmanager.register(
        subordinatePortnum, "debug", debugPassword,
        lambda mind, username : perspFactory(main, mind, username))
