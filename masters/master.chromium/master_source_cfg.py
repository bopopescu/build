# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import gitiles_poller


def Update(config, active_main, c):
  main_poller = gitiles_poller.GitilesPoller(
      'https://chromium.googlesource.com/chromium/src')

  c['change_source'].append(main_poller)
