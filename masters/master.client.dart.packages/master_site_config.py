# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class DartPackages(Main.Main3):
  project_name = 'Dart packages'
  main_port = 8079
  subordinate_port = 8179
  main_port_alt = 8279
  base_app_url = 'https://dart-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = base_app_url + '/lkgr'
  # This IP refers to a golem server in BigCluster
  http_status_push_url = "http://108.170.219.8:8080/submit-buildbot-info/"
  buildbot_url = 'http://build.chromium.org/p/client.dart.packages/'
