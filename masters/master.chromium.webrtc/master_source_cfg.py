# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import gitiles_poller


def Update(config, c):
  chromium_src_poller = gitiles_poller.GitilesPoller(
      config.Main.git_server_url + '/chromium/src',
      project='chromium')
  c['change_source'].append(chromium_src_poller)

  samples_poller = gitiles_poller.GitilesPoller(
      config.Main.git_server_url + '/external/webrtc-samples',
      project='webrtc-samples',
      comparator=chromium_src_poller.comparator)
  c['change_source'].append(samples_poller)
