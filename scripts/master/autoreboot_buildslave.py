# Copyright (c) 2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A subordinate that reboots after each job.

Yeah, we trust our unit tests *that* much.
"""

import os

from buildbot.buildsubordinate import BuildSubordinate


class AutoRebootBuildSubordinate(BuildSubordinate):
  def __init__(self, *args, **kwargs):
    """Enforces max_builds == 1 for obvious reasons."""
    kwargs['max_builds'] = 1
    BuildSubordinate.__init__(self, *args, **kwargs)

  def buildFinished(self, sb):
    """This is called when a build on this subordinate is finished."""
    flag_path = os.path.join(self.parent.main.basedir,
                             '.enable_perspective_shutdown')
    if os.path.exists(flag_path):
      # TODO(nodir): remove check when ready and deploy everywhere
      # Mark the build subordinate is to be shut down, so it does not accept jobs.
      self.perspective_shutdown()

    # Actually shutdown the subordinate.
    return self.shutdown()
