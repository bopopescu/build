# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumWebkit(Main.Main1):
  project_name = 'Chromium Webkit'
  main_port = 8014
  subordinate_port = 8114
  main_port_alt = 8214
  base_app_url = 'https://blink-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  buildbot_url = 'http://build.chromium.org/p/chromium.webkit/'
