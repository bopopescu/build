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

from buildbot.util import safeTranslate


class MainConfig(object):
    """
    Namespace for main configuration values.  An instance of this class is
    available at C{main.config}.

    @ivar changeHorizon: the current change horizon
    @ivar validation: regexes for preventing invalid inputs
    """

    changeHorizon = None

class BuilderConfig:
    """

    Used in config files to specify a builder - this can be subclassed by users
    to add extra config args, set defaults, or whatever.  It is converted to a
    dictionary for consumption by the buildmain at config time.

    """

    def __init__(self,
                name=None,
                subordinatename=None,
                subordinatenames=None,
                builddir=None,
                subordinatebuilddir=None,
                factory=None,
                category=None,
                nextSubordinate=None,
                nextBuild=None,
                nextSubordinateAndBuild=None,
                locks=None,
                env=None,
                properties=None,
                mergeRequests=None):

        # name is required, and can't start with '_'
        if not name or type(name) not in (str, unicode):
            raise ValueError("builder's name is required")
        if name[0] == '_':
            raise ValueError("builder names must not start with an "
                             "underscore: " + name)
        self.name = name

        # factory is required
        if factory is None:
            raise ValueError("builder's factory is required")
        self.factory = factory

        # subordinatenames can be a single subordinate name or a list, and should also
        # include subordinatename, if given
        if type(subordinatenames) is str:
            subordinatenames = [ subordinatenames ]
        if subordinatenames:
            if type(subordinatenames) is not list:
                raise TypeError("subordinatenames must be a list or a string")
        else:
            subordinatenames = []
        if subordinatename:
            if type(subordinatename) != str:
                raise TypeError("subordinatename must be a string")
            subordinatenames = subordinatenames + [ subordinatename ]
        if not subordinatenames:
            raise ValueError("at least one subordinatename is required")
        self.subordinatenames = subordinatenames

        # builddir defaults to name
        if builddir is None:
            builddir = safeTranslate(name)
        self.builddir = builddir

        # subordinatebuilddir defaults to builddir
        if subordinatebuilddir is None:
            subordinatebuilddir = builddir
        self.subordinatebuilddir = subordinatebuilddir

        # remainder are optional
        assert category is None or isinstance(category, str)
        self.category = category
        self.nextSubordinate = nextSubordinate
        self.nextBuild = nextBuild
        self.nextSubordinateAndBuild = nextSubordinateAndBuild
        self.locks = locks
        self.env = env
        self.properties = properties
        self.mergeRequests = mergeRequests

    def getConfigDict(self):
        rv = {
            'name': self.name,
            'subordinatenames': self.subordinatenames,
            'factory': self.factory,
            'builddir': self.builddir,
            'subordinatebuilddir': self.subordinatebuilddir,
        }
        if self.category:
            rv['category'] = self.category
        if self.nextSubordinate:
            rv['nextSubordinate'] = self.nextSubordinate
        if self.nextBuild:
            rv['nextBuild'] = self.nextBuild
        if self.nextSubordinateAndBuild:
            rv['nextSubordinateAndBuild'] = self.nextSubordinateAndBuild
        if self.locks:
            rv['locks'] = self.locks
        if self.env:
            rv['env'] = self.env
        if self.properties:
            rv['properties'] = self.properties
        if self.mergeRequests:
            rv['mergeRequests'] = self.mergeRequests
        return rv
