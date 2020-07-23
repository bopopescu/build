# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ActiveMain definition."""

from config_bootstrap import Main

class ChromiumOSTryServer(Main.ChromiumOSBase):
  project_name = 'ChromiumOS Try Server'
  main_port = 8049
  subordinate_port = 8149
  main_port_alt = 8249
  try_job_port = 8349
  buildbot_url = 'https://uberchromegw.corp.google.com/i/chromiumos.tryserver/'
  repo_url_ext = 'https://chromium.googlesource.com/chromiumos/tryjobs.git'
  repo_url_int = 'https://chrome-internal.googlesource.com/chromeos/tryjobs.git'
  from_address = 'cros.tryserver@chromium.org'
  # The reply-to address to set for emails sent from the server.
  reply_to = 'chromeos-build@google.com'
  # Select tree status urls and codereview location.
  base_app_url = 'https://chromiumos-status.appspot.com'
  tree_status_url = base_app_url + '/status'
  buildbucket_bucket = 'main.chromiumos.tryserver'
  service_account_file = 'service-account-chromeos.json'
