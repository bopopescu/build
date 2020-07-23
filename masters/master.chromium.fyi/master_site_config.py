# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumFYI(Main.Main1):
  project_name = 'Chromium FYI'
  main_port = 8011
  subordinate_port = 8111
  main_port_alt = 8211
  buildbot_url = 'http://build.chromium.org/p/chromium.fyi/'
  reboot_on_step_timeout = True
  pubsub_service_account_file = 'service-account-luci-milo.json'
  pubsub_topic_url = 'projects/luci-milo/topics/public-buildbot'
  name = 'chromium.fyi'
