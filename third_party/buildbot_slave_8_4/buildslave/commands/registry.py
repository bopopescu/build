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

from twisted.python import reflect

commandRegistry = {
    # command name : fully qualified factory name (callable)
    "shell" : "buildsubordinate.commands.shell.SubordinateShellCommand",
    "uploadFile" : "buildsubordinate.commands.transfer.SubordinateFileUploadCommand",
    "uploadDirectory" : "buildsubordinate.commands.transfer.SubordinateDirectoryUploadCommand",
    "downloadFile" : "buildsubordinate.commands.transfer.SubordinateFileDownloadCommand",
    "svn" : "buildsubordinate.commands.svn.SVN",
    "bk" : "buildsubordinate.commands.bk.BK",
    "cvs" : "buildsubordinate.commands.cvs.CVS",
    "darcs" : "buildsubordinate.commands.darcs.Darcs",
    "git" : "buildsubordinate.commands.git.Git",
    "repo" : "buildsubordinate.commands.repo.Repo",
    "bzr" : "buildsubordinate.commands.bzr.Bzr",
    "hg" : "buildsubordinate.commands.hg.Mercurial",
    "p4" : "buildsubordinate.commands.p4.P4",
    "p4sync" : "buildsubordinate.commands.p4.P4Sync",
    "mtn" : "buildsubordinate.commands.mtn.Monotone",
    "mkdir" : "buildsubordinate.commands.fs.MakeDirectory",
    "rmdir" : "buildsubordinate.commands.fs.RemoveDirectory",
    "cpdir" : "buildsubordinate.commands.fs.CopyDirectory",
    "stat" : "buildsubordinate.commands.fs.StatFile",
}

def getFactory(command):
    factory_name = commandRegistry[command]
    factory = reflect.namedObject(factory_name)
    return factory

def getAllCommandNames():
    return commandRegistry.keys()
