# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class WebRTCFYI(Main.Main3):
  project_name = 'WebRTC FYI'
  main_port = 8072
  subordinate_port = 8172
  main_port_alt = 8272
  server_url = 'http://webrtc.googlecode.com'
  project_url = 'http://webrtc.googlecode.com'
  from_address = 'webrtc-cb-fyi-watchlist@google.com'
  buildbot_url = 'http://build.chromium.org/p/client.webrtc.fyi/'
  service_account_file = 'service-account-webrtc.json'
  buildbucket_bucket = 'main.client.webrtc.fyi'
