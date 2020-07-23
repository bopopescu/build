# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Mojo(Main.Main3):
  project_name = 'Mojo'
  main_port = 8019
  subordinate_port = 8119
  main_port_alt = 8219
  buildbot_url = 'http://build.chromium.org/p/client.mojo/'
  service_account_file = 'service-account-chromium-tryserver.json'
  buidlbucket_build = 'main.tryserver.client.mojo'
