# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Libyuv(Main.Main3):
  project_name = 'Libyuv'
  main_port = 8062
  subordinate_port = 8162
  main_port_alt = 8262
  buildbot_url = 'http://build.chromium.org/p/client.libyuv/'
  server_url = 'https://chromium.googlesource.com/libyuv/libyuv'
  project_url = 'https://code.google.com/p/libyuv/'
  from_address = 'libyuv-cb-watchlist@google.com'
  permitted_domains = ('google.com', 'chromium.org', 'webrtc.org')
