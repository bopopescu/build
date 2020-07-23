# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class V8Ports(Main.Main3a):
  base_app_url = 'https://v8-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = base_app_url + '/lkgr'
  project_name = 'V8 Ports'
  main_port_id = 17
  project_url = 'https://developers.google.com/v8/'
  buildbot_url = 'http://build.chromium.org/p/client.v8.ports/'
  service_account_file = 'service-account-v8.json'
