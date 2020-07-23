# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumChrome(Main.Main1):
  project_name = 'Chromium Chrome'
  main_port = 8015
  subordinate_port = 8115
  main_port_alt = 8215
  buildbot_url = 'http://build.chromium.org/p/chromium.chrome/'
