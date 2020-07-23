# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file was generated from
# scripts/tools/buildbot_tool_templates/main_site_config.py
# by "../../build/scripts/tools/buildbot-tool gen .".
# DO NOT EDIT BY HAND!


"""ActiveMain definition."""

from config_bootstrap import Main

class CustomTabsClientTryserver(Main.Main4a):
  project_name = 'CustomTabsClientTryserver'
  main_port = 20400
  subordinate_port = 30400
  main_port_alt = 25400
  buildbot_url = 'https://build.chromium.org/p/tryserver.client.custom_tabs_client/'
  buildbucket_bucket = 'main.tryserver.client.custom_tabs_client'
  service_account_file = 'service-account-chromium-tryserver.json'
