# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Syzygy(Main.Main3):
  project_name = 'Syzygy'
  project_url = 'http://www.github.com/google/syzygy'
  main_port = 8042
  subordinate_port = 8142
  main_port_alt = 8242
  buildbot_url = 'https://build.chromium.org/p/client.syzygy/'
