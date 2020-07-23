# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main.v8.v8_notifier import V8Notifier


def Update(config, active_main, c):
  c['status'].extend([
    V8Notifier(
        config,
        active_main,
        categories_steps={
          'chromium': [
            'update',
            'runhooks',
            'gn',
            'compile',
          ],
        },
        sendToInterestedUsers=True,
    ),
    V8Notifier(
        config,
        active_main,
        categories_steps={
          'clusterfuzz': [
            'check clusterfuzz'
            'runhooks',
            'gn',
            'compile',
            'gsutil upload',
          ],
        },
        extraRecipients=[
          'machenbach@chromium.org',
          'v8-clusterfuzz-sheriff@chromium.org',
        ],
    ),
    V8Notifier(
        config,
        active_main,
        categories_steps={'release': []},
        extraRecipients=[
          'hablich@chromium.org',
          'machenbach@chromium.org',
        ],
    ),
  ])

