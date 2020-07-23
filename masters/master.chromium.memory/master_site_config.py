# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumMemory(Main.Main1):
  project_name = 'Chromium Memory'
  main_port = 8012
  subordinate_port = 8112
  main_port_alt = 8212
  buildbot_url = 'http://build.chromium.org/p/chromium.memory/'
