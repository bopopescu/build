# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class InfraCron(Main.Main1):
  project_name = 'InfraCron'
  main_port_id = 12
  buildbot_url = 'https://build.chromium.org/p/chromium.infra.cron/'
  service_account_file = 'service-account-infra-cron.json'
  buildbucket_bucket = 'main.chromium.infra.cron'
