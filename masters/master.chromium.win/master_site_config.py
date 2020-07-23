# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumWin(Main.Main1):
  project_name = 'Chromium Win'
  main_port = 8085
  subordinate_port = 8185
  main_port_alt = 8285
  buildbot_url = 'http://build.chromium.org/p/chromium.win/'
