# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import gitiles_poller


def Update(config, c):
  webrtc_repo_url = config.Main.git_server_url + '/external/webrtc/'
  webrtc_poller = gitiles_poller.GitilesPoller(webrtc_repo_url,
                                               project='webrtc')
  c['change_source'].append(webrtc_poller)
