# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from main.factory import annotator_factory


AF = annotator_factory.AnnotatorFactory()


# Windows binaries smoke-test builder for Syzygy.
smoke_test_builder = {
  'name': 'Syzygy Smoke Test',
  'factory': AF.BaseFactory(recipe='syzygy/smoke_test'),
  'auto_reboot': False,
  'category': 'official',
}


def Update(config, active_main, c):
  c['builders'].append(smoke_test_builder)
