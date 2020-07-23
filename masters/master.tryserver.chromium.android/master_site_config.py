# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file was generated from
# scripts/tools/buildbot_tool_templates/main_site_config.py
# by "../../build/scripts/tools/buildbot-tool gen .".
# DO NOT EDIT BY HAND!


"""ActiveMain definition."""

from config_bootstrap import Main

class TryserverChromiumAndroid(Main.Main4a):
  project_name = 'TryserverChromiumAndroid'
  main_port = 21401
  subordinate_port = 31401
  main_port_alt = 26401
  buildbot_url = 'https://build.chromium.org/p/tryserver.chromium.android/'
  buildbucket_bucket = 'main.tryserver.chromium.android'
  service_account_file = 'service-account-chromium-tryserver.json'
