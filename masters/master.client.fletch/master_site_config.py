# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Dartino(Main.Main3):
  base_app_url = 'https://dart-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  project_name = 'Dart'
  main_port = 20316
  subordinate_port = 30316
  # Enable when there's a public waterfall.
  main_port_alt = 25316
  buildbot_url = 'http://build.chromium.org/p/client.fletch/'
