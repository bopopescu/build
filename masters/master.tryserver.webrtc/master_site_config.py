# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class WebRTCTryServer(Main.Main4):
  project_name = 'WebRTC Try Server'
  main_port = 8070
  subordinate_port = 8170
  main_port_alt = 8270
  try_job_port = 8370
  from_address = 'tryserver@webrtc.org'
  reply_to = 'chrome-troopers+tryserver@google.com'
  svn_url = 'svn://svn-mirror.golo.chromium.org/chrome-try/try-webrtc'
  base_app_url = 'https://webrtc-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = None
  code_review_site = 'https://codereview.webrtc.org'
  buildbot_url = 'http://build.chromium.org/p/tryserver.webrtc/'
  service_account_file = 'service-account-webrtc.json'
  buildbucket_bucket = 'main.tryserver.webrtc'
