# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumChromeDriver(Main.Main1):
  project_name = 'Chromium ChromeDriver'
  main_port = 8016
  subordinate_port = 8116
  main_port_alt = 8216
  buildbot_url = 'http://build.chromium.org/p/chromium.chromedriver/'
