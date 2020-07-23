# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumGPUFYI(Main.Main1):
  project_name = 'Chromium GPU FYI'
  main_port = 8017
  subordinate_port = 8117
  main_port_alt = 8217
  buildbot_url = 'http://build.chromium.org/p/chromium.gpu.fyi/'
