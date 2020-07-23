# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class WebPorts(Main.NaClBase):
  project_name = 'WebPorts'
  main_port = 8035
  subordinate_port = 8135
  main_port_alt = 8235
  base_app_url = 'https://naclports-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = base_app_url + '/lkgr'
  buildbot_url = 'http://build.chromium.org/p/client.nacl.ports/'
