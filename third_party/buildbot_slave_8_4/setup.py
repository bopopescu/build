#!/usr/bin/env python
#
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

"""
Standard setup script.
"""

import sys
import os
from distutils.core import setup
from distutils.command.install_data import install_data
from distutils.command.sdist import sdist

from buildsubordinate import version

scripts = ["bin/buildsubordinate"]
# sdist is usually run on a non-Windows platform, but the buildsubordinate.bat file
# still needs to get packaged.
if 'sdist' in sys.argv or sys.platform == 'win32':
    scripts.append("contrib/windows/buildsubordinate.bat")
    scripts.append("contrib/windows/buildbot_service.py")

class our_install_data(install_data):

    def finalize_options(self):
        self.set_undefined_options('install',
            ('install_lib', 'install_dir'),
        )
        install_data.finalize_options(self)

    def run(self):
        install_data.run(self)
        # ensure there's a buildsubordinate/VERSION file
        fn = os.path.join(self.install_dir, 'buildsubordinate', 'VERSION')
        open(fn, 'w').write(version)
        self.outfiles.append(fn)

class our_sdist(sdist):

    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        # ensure there's a buildsubordinate/VERSION file
        fn = os.path.join(base_dir, 'buildsubordinate', 'VERSION')
        open(fn, 'w').write(version)

setup_args = {
    'name': "buildbot-subordinate",
    'version': version,
    'description': "BuildBot Subordinate Daemon",
    'long_description': "See the 'buildbot' package for details",
    'author': "Brian Warner",
    'author_email': "warner-buildbot@lothar.com",
    'maintainer': "Dustin J. Mitchell",
    'maintainer_email': "dustin@v.igoro.us",
    'url': "http://buildbot.net/",
    'license': "GNU GPL",
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
        ],

    'packages': [
        "buildsubordinate",
        "buildsubordinate.commands",
        "buildsubordinate.scripts",
        "buildsubordinate.monkeypatches",
        "buildsubordinate.test",
        "buildsubordinate.test.fake",
        "buildsubordinate.test.util",
        "buildsubordinate.test.unit",
    ],
    'scripts': scripts,
    # mention data_files, even if empty, so install_data is called and
    # VERSION gets copied
    'data_files': [("buildsubordinate", [])],
    'cmdclass': {
        'install_data': our_install_data,
        'sdist': our_sdist
        }
    }

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools #@UnusedImport
except ImportError:
    pass
else:
    setup_args['install_requires'] = [
        'twisted >= 8.0.0',
    ]

    if os.getenv('NO_INSTALL_REQS'):
        setup_args['install_requires'] = None

setup(**setup_args)
