# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Site configuration information that is sufficient to configure a subordinate,
without loading any buildbot or twisted code.
"""

import inspect
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Override config_default with a config_private file.
BASE_MASTERS = []
try:
  import config_private # pylint: disable=F0401
  BASE_MASTERS += [config_private.Main, config_private.PublicMain]
except ImportError:
  import config_default as config_private # pylint: disable=W0403
  BASE_MASTERS += [config_private.Main,]


class Main(config_private.Main):
  """Buildbot main configuration options."""

  trunk_url = (config_private.Main.server_url +
               config_private.Main.repo_root + '/trunk')

  webkit_trunk_url = (config_private.Main.webkit_root_url + '/trunk')

  trunk_url_src = config_private.Main.git_server_url + '/chromium/src.git'

  dart_url = config_private.Main.googlecode_url % 'dart'
  dart_bleeding = dart_url + '/branches/bleeding_edge'
  dart_trunk = dart_url + '/trunk'

  # Default target platform if none was given to the factory.
  default_platform = 'win32'

  # Used by the waterfall display.
  project_url = 'http://www.chromium.org'

  # Base URL for perf test results.
  perf_base_url = 'http://build.chromium.org/f/chromium/perf'

  # Suffix for perf URL.
  perf_report_url_suffix = 'report.html?history=150'

  # Directory in which to save perf-test output data files.
  perf_output_dir = '~/www/perf'

  # URL pointing to builds and test results.
  archive_url = 'http://build.chromium.org/buildbot'

  # The test results server to upload our test results.
  test_results_server = 'test-results.appspot.com'

  # File in which to save a list of graph names.
  perf_graph_list = 'graphs.dat'

  # Magic step return code inidicating "warning(s)" rather than "error".
  retcode_warnings = 88

  @staticmethod
  def GetBotPassword():
    """Returns the subordinate password retrieved from a local file, or None.

    The subordinate password is loaded from a local file next to this module file, if
    it exists.  This is a function rather than a variable so it's not called
    when it's not needed.

    We can't both make this a property and also keep it static unless we use a
    <metaclass, which is overkill for this usage.
    """
    # Note: could be overriden by config_private.
    if not getattr(Main, 'bot_password', None):
      # If the bot_password has been requested, the file is required to exist
      # if not overriden in config_private.
      bot_password_path = os.path.join(BASE_DIR, '.bot_password')
      Main.bot_password = open(bot_password_path).read().strip('\n\r')
    return Main.bot_password

  @staticmethod
  def _extract_mains(main):
    return [v for v in main.__dict__.itervalues()
            if (inspect.isclass(v) and
                issubclass(v, config_private.Main.Base) and
                v != config_private.Main.Base)]

  @classmethod
  def get_base_mains(cls):
    mains = []
    for base_main in BASE_MASTERS:
      mains += cls._extract_mains(base_main)
    return mains

  @classmethod
  def get_all_mains(cls):
    return cls._extract_mains(cls)
