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

import mock

def make_main():
    """
    Create a fake Main instance: a Mock with some convenience
    implementations:

    - Non-caching implementation for C{self.caches}
    """

    fakemain = mock.Mock(name="fakemain")

    # set up caches
    def fake_get_cache(name, miss_fn):
        fake_cache = mock.Mock(name='fakemain.caches[%r]' % name)
        fake_cache.get = miss_fn
        return fake_cache
    fakemain.caches.get_cache = fake_get_cache

    return fakemain
