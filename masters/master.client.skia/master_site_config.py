# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""


from common.skia import global_constants
from config_bootstrap import Main


class Skia(Main.Main3):
  project_name = 'Skia'
  main_port = 8084
  subordinate_port = 8184
  main_port_alt = 8284
  repo_url = global_constants.SKIA_REPO
  buildbot_url = 'http://build.chromium.org/p/client.skia/'
  service_account_file = global_constants.SERVICE_ACCOUNT_FILE
  buildbucket_bucket = 'main.client.skia'
