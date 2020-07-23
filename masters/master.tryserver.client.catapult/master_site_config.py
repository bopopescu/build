# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file was generated from
# scripts/tools/buildbot_tool_templates/main_site_config.py
# by "../../build/scripts/tools/buildbot-tool gen .".
# DO NOT EDIT BY HAND!


"""ActiveMain definition."""

from config_bootstrap import Main

class CatapultTryserver(Main.Main4a):
  project_name = 'CatapultTryserver'
  main_port = 21400
  subordinate_port = 31400
  main_port_alt = 26400
  buildbot_url = 'https://build.chromium.org/p/tryserver.client.catapult/'
  buildbucket_bucket = 'main.tryserver.client.catapult'
  service_account_file = 'service-account-chromium-tryserver.json'
