# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'chromite',
  'gitiles',
  'recipe_engine/properties',
]


# Map main name to 'chromite' configuration name.
_MASTER_CONFIG_MAP = {
  'chromiumos': {
    'main_config': 'main_chromiumos',
    'variants': {
      'paladin': ['chromiumos_paladin'],
    },
  },
  'chromiumos.chromium': {
    'main_config': 'main_chromiumos_chromium',
  },

  # Fake waterfall for Coverage
  'chromiumos.coverage': {
    'main_config': 'main_chromiumos',
    'variants': {
      'test': ['chromiumos_coverage_test'],
    },
  },
}

def RunSteps(api):
  # Load the appropriate configuration based on the main.
  api.chromite.configure(
      api.properties,
      _MASTER_CONFIG_MAP)

  # Run 'cbuildbot' common recipe.
  api.chromite.run_cbuildbot()

def GenTests(api):
  #
  # main.chromiumos.chromium
  #

  # Test a standard CrOS build triggered by a Chromium commit.
  yield (
      api.test('chromiumos_chromium_builder')
      + api.properties(
          mainname='chromiumos.chromium',
          buildername='Test',
          subordinatename='test',
          buildnumber='12345',
          repository='https://chromium.googlesource.com/chromium/src',
          revision='b8819267417da248aa4fe829c5fcf0965e17b0c3',
          branch='main',
          cbb_config='x86-generic-tot-chrome-pfq-informational',
      )
  )

  #
  # main.chromiumos
  #

  # Test a ChromiumOS Paladin build.
  yield (
      api.test('chromiumos_paladin')
      + api.properties(
          mainname='chromiumos',
          buildername='Test',
          subordinatename='test',
          buildnumber='12345',
          repository='https://chromium.googlesource.com/chromiumos/'
                     'manifest-versions',
          branch='main',
          revision=api.gitiles.make_hash('test'),
          cbb_config='x86-generic-paladin',
          cbb_variant='paladin',
      )
      + api.step_data(
          'Fetch manifest config',
          api.gitiles.make_commit_test_data(
              'test',
              '\n'.join([
                  'Commit message!',
                  'Automatic: Start main-paladin main 6952.0.0-rc4',
                  'CrOS-Build-Id: 1337',
              ]),
          ),
      )
  )

  # Test a ChromiumOS Paladin build whose manifest is not parsable.
  yield (
      api.test('chromiumos_paladin_manifest_failure')
      + api.properties(
          mainname='chromiumos',
          buildername='Test',
          subordinatename='test',
          buildnumber='12345',
          repository='https://chromium.googlesource.com/chromiumos/'
                     'manifest-versions',
          branch='main',
          revision=api.gitiles.make_hash('test'),
          cbb_config='x86-generic-paladin',
          cbb_variant='paladin',
      )
      + api.step_data(
          'Fetch manifest config',
          api.gitiles.make_commit_test_data(
              'test',
              None
          )
      )
  )

  #
  # [Coverage]
  #

  # Coverage builders for a bunch of options used in other repositories.
  yield (
      api.test('chromiumos_coverage')
      + api.properties(
          mainname='chromiumos.coverage',
          buildername='Test',
          subordinatename='test',
          buildnumber=0,
          clobber=None,
          repository='https://chromium.googlesource.com/chromiumos/'
                     'chromite.git',
          revision='fdea0dde664e229976ddb2224328da152fba15b1',
          branch='main',
          cbb_config='x86-generic-full',
          cbb_branch='factory-1412.B',
          cbb_variant='test',
          cbb_debug=True,
          cbb_disable_branch=True,
          config_repo='https://fake.googlesource.com/myconfig/repo.git',
      )
  )
