# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""


from common.skia import global_constants
from config_bootstrap import Main


class SkiaCompile(Main.Main3):
  project_name = 'SkiaCompile'
  main_port = 8095
  subordinate_port = 8195
  main_port_alt = 8295
  repo_url = global_constants.SKIA_REPO
  buildbot_url = 'http://build.chromium.org/p/client.skia.compile/'
  service_account_file = global_constants.SERVICE_ACCOUNT_FILE
  buildbucket_bucket = 'main.client.skia.compile'
