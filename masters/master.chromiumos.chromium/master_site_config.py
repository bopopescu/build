# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumOSChromium(Main.Main2):
  project_name = 'ChromiumOS Chromium'
  main_port = 8073
  subordinate_port = 8173
  main_port_alt = 8273
  buildbot_url = 'http://build.chromium.org/p/chromiumos.chromium/'
