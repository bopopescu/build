# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class TryServerChromiumLinux(Main.Main4a):
  project_name = 'Chromium Linux Try Server'
  main_port = 8092
  subordinate_port = 8192
  main_port_alt = 8292
  try_job_port = 8392
  # Select tree status urls and codereview location.
  reply_to = 'chrome-troopers+tryserver@google.com'
  base_app_url = 'https://chromium-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = None
  last_good_blink_url = None
  svn_url = 'svn://svn-mirror.golo.chromium.org/chrome-try/try'
  buildbot_url = 'http://build.chromium.org/p/tryserver.chromium.linux/'
  service_account_file = 'service-account-chromium-tryserver.json'
  buildbucket_bucket = 'main.tryserver.chromium.linux'
