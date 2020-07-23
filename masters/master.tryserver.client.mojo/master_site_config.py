# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class MojoTryServer(Main.Main4a):
  project_name = 'Mojo Try Server'
  main_port = 21410
  subordinate_port = 31410
  main_port_alt = 26410
  buildbot_url = 'https://build.chromium.org/p/tryserver.client.mojo/'
  service_account_file = 'service-account-mojo.json'
  buildbucket_bucket = 'main.tryserver.client.mojo'
