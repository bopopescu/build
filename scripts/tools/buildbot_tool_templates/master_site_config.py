# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file is used by scripts/tools/buildbot-tool to generate main configs.

"""ActiveMain definition."""

from config_bootstrap import Main

class %(main_classname)s(Main.%(main_base_class)s):
  project_name = '%(main_classname)s'
  main_port = %(main_port)s
  subordinate_port = %(subordinate_port)s
  main_port_alt = %(main_port_alt)s
  buildbot_url = '%(buildbot_url)s'
  buildbucket_bucket = %(buildbucket_bucket_str)s
  service_account_file = %(service_account_file_str)s
