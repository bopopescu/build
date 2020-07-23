# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumPerf(Main.Main1):
  project_name = 'Chromium Perf'
  main_port = 8013
  subordinate_port = 8113
  main_port_alt = 8213
  buildbot_url = 'http://build.chromium.org/p/chromium.perf/'
  service_account_file = 'service-account-chromium.json'
  buildbucket_bucket = 'main.chromium.perf'
