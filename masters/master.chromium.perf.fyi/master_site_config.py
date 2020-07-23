# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumPerfFyi(Main.Main1):
  project_name = 'Chromium Perf Fyi'
  main_port = 8061
  subordinate_port = 8161
  main_port_alt = 8261
  buildbot_url = 'http://build.chromium.org/p/chromium.perf.fyi/'
  service_account_file = 'service-account-chromium.json'
  buildbucket_bucket = 'main.chromium.perf.fyi'
