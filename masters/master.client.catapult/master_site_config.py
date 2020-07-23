# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file was generated from
# scripts/tools/buildbot_tool_templates/main_site_config.py
# by "../../build/scripts/tools/buildbot-tool gen .".
# DO NOT EDIT BY HAND!


"""ActiveMain definition."""

from config_bootstrap import Main

class Catapult(Main.Main3):
  project_name = 'Catapult'
  main_port = 20303
  subordinate_port = 30303
  main_port_alt = 25303
  buildbot_url = 'https://build.chromium.org/p/client.catapult/'
  buildbucket_bucket = None
  service_account_file = None
