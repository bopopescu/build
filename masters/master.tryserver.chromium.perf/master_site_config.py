# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumPerfTryServer(Main.Main4):
  project_name = 'Chromium Perf Try Server'
  main_port = 8041
  subordinate_port = 8141
  main_port_alt = 8241
  try_job_port = 8341
  buildbot_url = 'http://build.chromium.org/p/tryserver.chromium.perf/'
  # Select tree status urls and codereview location.
  reply_to = 'chrome-troopers+tryserver@google.com'
  base_app_url = 'https://chromium-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  svn_url = 'svn://svn.chromium.org/chrome-try/try-perf'
  last_good_url = base_app_url + '/lkgr'
  service_account_file = 'service-account-chromium-tryserver.json'
  buildbucket_bucket = 'main.tryserver.chromium.perf'
