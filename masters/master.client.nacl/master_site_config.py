# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class NativeClient(Main.NaClBase):
  project_name = 'NativeClient'
  main_port = 8030
  subordinate_port = 8130
  main_port_alt = 8230
  buildbot_url = 'http://build.chromium.org/p/client.nacl/'
