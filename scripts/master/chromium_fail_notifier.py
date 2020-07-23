# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A StatusReceiver module to mail someone when a step fails.

Since the behavior is very similar to the ChromiumNotifier, we simply
inherit from it.
"""

from buildbot.status.builder import FAILURE

from main.chromium_notifier import ChromiumNotifier

class ChromiumFailNotifier(ChromiumNotifier):
  """This is a status notifier emails on step failures. """
  # Overloaded functions need to be member even if they don't access self.
  # pylint: disable=R0201,W0221

  def __init__(self, **kwargs):
    """Constructor just passes through.  """
    ChromiumNotifier.__init__(self, **kwargs)

  def isInterestingStep(self, build_status, step_status, results):
    """Watch only steps that Fail. """
    return results[0] == FAILURE
