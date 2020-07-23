# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildbot.status.builder import FAILURE
from main import chromium_notifier
from main import main_utils


FORGIVING_STEPS = [
  'update_scripts',
  'svnkill',
  'taskkill',
]


class V8Notifier(chromium_notifier.ChromiumNotifier):
  def __init__(self,
               config,
               active_main,
               categories_steps,
               sendToInterestedUsers=False,
               extraRecipients=None):
    extraRecipients = extraRecipients or []
    chromium_notifier.ChromiumNotifier.__init__(
        self,
        fromaddr=active_main.from_address,
        categories_steps=categories_steps,
        relayhost=config.Main.smtp,
        sendToInterestedUsers=sendToInterestedUsers,
        extraRecipients=extraRecipients,
        status_header=
            'buildbot failure in %(project)s on %(builder)s, %(steps)s',
        lookup=main_utils.FilterDomain(),
        forgiving_steps=FORGIVING_STEPS,
    )

  def isInterestingStep(self, build_status, step_status, results):
    """Watch only failing steps."""
    return results[0] == FAILURE

