# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumLKGR(Main.Main1):
  project_name = 'Chromium LKGR'
  main_port = 8018
  subordinate_port = 8118
  main_port_alt = 8218
  poll_url = 'https://chromium-status.appspot.com/lkgr'
  buildbot_url = 'http://build.chromium.org/p/chromium.lkgr/'
