# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class LibyuvTryServer(Main.Main4):
  project_name = 'Libyuv Try Server'
  main_port = 8006
  subordinate_port = 8106
  main_port_alt = 8206
  try_job_port = 8306
  from_address = 'libyuv-cb-watchlist@google.com'
  reply_to = 'chrome-troopers+tryserver@google.com'
  code_review_site = 'https://codereview.chromium.org'
  svn_url = 'svn://svn-mirror.golo.chromium.org/chrome-try/try-libyuv'
  buildbot_url = 'http://build.chromium.org/p/tryserver.libyuv/'
  service_account_file = 'service-account-libyuv.json'
  buildbucket_bucket = 'main.tryserver.libyuv'
