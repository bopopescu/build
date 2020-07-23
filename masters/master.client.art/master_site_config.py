# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ART(Main.Main3):
  project_name = 'ART'
  main_port = 8200
  subordinate_port = 8300
  main_port_alt = 8400
  buildbot_url = 'http://build.chromium.org/p/client.art/'
