# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file was generated from
# scripts/tools/buildbot_tool_templates/main_site_config.py
# by "../../build/scripts/tools/buildbot-tool gen .".
# DO NOT EDIT BY HAND!


"""ActiveMain definition."""

from config_bootstrap import Main

class ClientLegion(Main.Main3):
  project_name = 'ClientLegion'
  main_port = 20315
  subordinate_port = 30315
  main_port_alt = 25315
  buildbot_url = 'https://build.chromium.org/p/client.legion/'
  buildbucket_bucket = None
  service_account_file = None
