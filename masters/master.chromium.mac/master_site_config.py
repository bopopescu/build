# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumMac(Main.Main1):
  project_name = 'Chromium Mac'
  main_port = 8086
  subordinate_port = 8186
  main_port_alt = 8286
  buildbot_url = 'http://build.chromium.org/p/chromium.mac/'
