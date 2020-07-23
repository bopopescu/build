# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import gitiles_poller
from main import main_config


helper = main_config.Helper({})
helper.Scheduler('chromium_src', branch='main', treeStableTimer=60)

def Update(config, _active_main, c):
  main_poller = gitiles_poller.GitilesPoller(
      'https://chromium.googlesource.com/chromium/src')
  c['change_source'].append(main_poller)
  return helper.Update(c)
