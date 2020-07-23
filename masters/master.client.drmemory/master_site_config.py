# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class DrMemory(Main.Main3):
  project_name = 'DrMemory'
  main_port = 8058
  subordinate_port = 8158
  main_port_alt = 8258
  buildbot_url = 'http://build.chromium.org/p/client.drmemory/'
