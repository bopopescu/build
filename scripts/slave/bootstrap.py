# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to enable subordinates to determine their main without importing any
buildbot or twisted code.
"""

import inspect
import os
import sys

from common import chromium_utils
import config_bootstrap


def ImportMainConfigs(main_name=None, include_internal=True):
  """Imports main configs.

  Normally a subordinate can use chromium_utils.GetActiveMain() to find
  itself and determine which ActiveMain to use.  In that case, the
  active main name is passed in as an arg, and we only load the
  site_config.py that defines it.  When testing, the current "subordinate"
  won't be found.  In that case, we don't know which config to use, so
  load them all.  In either case, mains are assigned as attributes
  to the config.Main object.
  """
  for main in chromium_utils.ListMains(include_internal=include_internal):
    path = os.path.join(main, 'main_site_config.py')
    if os.path.exists(path):
      local_vars = {}
      try:
        execfile(path, local_vars)
      # pylint: disable=W0703
      except Exception, e:
        # Naked exceptions are banned by the style guide but we are
        # trying to be resilient here.
        print >> sys.stderr, 'WARNING: cannot exec ' + path
        print >> sys.stderr, e
      for (symbol_name, symbol) in local_vars.iteritems():
        if inspect.isclass(symbol):
          setattr(symbol, 'local_config_path', main)
          setattr(config_bootstrap.Main, symbol_name, symbol)
          # If we have a main_name and it matches, set
          # config_bootstrap.Main.active_main.
          if main_name and main_name == symbol_name:
            setattr(config_bootstrap.Main, 'active_main', symbol)
