# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class TryServerANGLE(Main.Main4a):
  project_name = 'ANGLE Try Server'
  main_port = 21403
  subordinate_port = 31403
  main_port_alt = 26403
  buildbot_url = 'http://build.chromium.org/p/tryserver.chromium.angle/'
  gerrit_host = 'https://chromium-review.googlesource.com'
  service_account_file = 'service-account-chromium-tryserver.json'
  buildbucket_bucket = 'main.tryserver.chromium.angle'
