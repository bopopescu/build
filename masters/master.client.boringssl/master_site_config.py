# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Boringssl(Main.Main3):
  project_name = 'Boringssl'
  project_url = 'https://boringssl.googlesource.com/boringssl/'
  main_port = 20311
  subordinate_port = 30311
  main_port_alt = 25311
  buildbot_url = 'http://build.chromium.org/p/client.boringssl/'
