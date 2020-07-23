# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class Libvpx(Main.Main3):
  project_name = 'Libvpx'
  main_port = 8037
  subordinate_port = 8137
  main_port_alt = 8237
  buildbot_url = 'http://build.chromium.org/p/client.libvpx/'
  source_url = 'https://chromium.googlesource.com/webm/libvpx'
