# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class NativeClientSDK(Main.NaClBase):
  project_name = 'NativeClientSDK'
  main_port = 8034
  subordinate_port = 8134
  main_port_alt = 8234
  buildbot_url = 'http://build.chromium.org/p/client.nacl.sdk/'
