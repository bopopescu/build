# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main import main_config
from main.factory import annotator_factory


defaults = {'category': 'continuous'}
helper = main_config.Helper(defaults)
B = helper.Builder
D = helper.Dependent
F = helper.Factory
S = helper.Scheduler
AF = annotator_factory.AnnotatorFactory()


# Continous build scheduler for Syzygy.
S('syzygy_cont', branch='main', treeStableTimer=60)


# Windows continuous Release builder.
B('Syzygy Release', 'f_syzygy_win_rel', scheduler='syzygy_cont',
  auto_reboot=False)
F('f_syzygy_win_rel', AF.BaseFactory(recipe='syzygy/continuous'))


# Windows continuous Debug builder.
B('Syzygy Debug', 'f_syzygy_win_dbg', scheduler='syzygy_cont',
  auto_reboot=False)
F('f_syzygy_win_dbg', AF.BaseFactory(recipe='syzygy/continuous'))


# Windows continuous code coverage builder.
B('Syzygy Coverage', 'f_syzygy_win_cov', scheduler='syzygy_cont',
  auto_reboot=False)
F('f_syzygy_win_cov', AF.BaseFactory(recipe='syzygy/coverage'))


def Update(config, active_main, c):
  return helper.Update(c)
