# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Chromium(Main.Main1):
  project_name = 'Chromium'
  main_port = 8010
  subordinate_port = 8110
  main_port_alt = 8210
  buildbot_url = 'http://build.chromium.org/p/chromium/'
