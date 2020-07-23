# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import chromium_notifier
from main import main_utils

# This is the list of the builder categories and the corresponding critical
# steps.
# Note: don't include 'update scripts' since we can't do much about it when
# it's failing and the tree is still technically fine.
gardener_categories_steps = {
  '': [],
  'pfq': ['cbuildbot'],
}

memory_categories_steps = {
  '': [],
  'crosasantest': ['VMTest'],
}

exclusions = {
}

forgiving_steps = ['update_scripts', 'update', 'gclient_revert']

warning_header = ('Please look at failure in "%(steps)s" on "%(builder)s" '
                  'and help out if you can')


def Update(config, active_main, c):
  c['status'].append(chromium_notifier.ChromiumNotifier(
      fromaddr=active_main.from_address,
      categories_steps=gardener_categories_steps,
      exclusions=exclusions,
      relayhost=config.Main.smtp,
      subject='buildbot %(result)s in %(projectName)s on %(builder)s, '
              'revision %(revision)s',
      status_header=warning_header,
      extraRecipients=active_main.tree_closing_notification_recipients,
      lookup=main_utils.FilterDomain(),
      forgiving_steps=forgiving_steps,
      public_html='../main.chromiumos/public_html',
      sheriffs=['sheriff_cr_cros_gardeners'],
      use_getname=True))
  c['status'].append(chromium_notifier.ChromiumNotifier(
      fromaddr=active_main.from_address,
      categories_steps=memory_categories_steps,
      exclusions=exclusions,
      relayhost=config.Main.smtp,
      subject='buildbot %(result)s in %(projectName)s on %(builder)s, '
              'revision %(revision)s',
      status_header=warning_header,
      extraRecipients=active_main.tree_closing_notification_recipients,
      lookup=main_utils.FilterDomain(),
      forgiving_steps=forgiving_steps,
      public_html='../main.chromiumos/public_html',
      sheriffs=['sheriff_memory'],
      use_getname=True))
