# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumMemoryFYI(Main.Main1):
  project_name = 'Chromium Memory FYI'
  main_port = 8025
  subordinate_port = 8125
  main_port_alt = 8225
  buildbot_url = 'http://build.chromium.org/p/chromium.memory.fyi/'
