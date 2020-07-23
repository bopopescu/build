# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class WebRTC(Main.Main3):
  project_name = 'WebRTC'
  main_port = 8060
  subordinate_port = 8160
  main_port_alt = 8260
  server_url = 'http://webrtc.googlecode.com'
  project_url = 'http://webrtc.googlecode.com'
  from_address = 'webrtc-cb-watchlist@google.com'
  tree_closing_notification_recipients = ['webrtc-cb-watchlist@google.com']
  main_domain = 'webrtc.org'
  permitted_domains = ('google.com', 'chromium.org', 'webrtc.org')
  base_app_url = 'https://webrtc-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  store_revisions_url = base_app_url + '/revisions'
  last_good_url = base_app_url + '/lkgr'
  buildbot_url = 'http://build.chromium.org/p/client.webrtc/'
  service_account_file = 'service-account-webrtc.json'
  buildbucket_bucket = 'main.client.webrtc'
