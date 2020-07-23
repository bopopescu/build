# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Recipe module for Skia Swarming test.


DEPS = [
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'skia',
]


TEST_BUILDERS = {
  'client.skia': {
    'skiabot-linux-tester-000': [
      'Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug',
    ],
    'skiabot-win-tester-000': [
      'Test-Win8-MSVC-ShuttleB-CPU-AVX2-x86_64-Release-Trybot'
    ],
    'skiabot-nexus6-001': [
      'Test-Android-GCC-Nexus6-GPU-Adreno420-Arm7-Release',
    ],
  },
}


def RunSteps(api):
  api.skia.setup(running_in_swarming=True)
  api.skia.test_steps()
  api.skia.cleanup_steps()


def GenTests(api):
  def AndroidTestData(builder):
    test_data = (
        api.step_data(
            'get EXTERNAL_STORAGE dir',
            stdout=api.raw_io.output('/storage/emulated/legacy')) +
        api.step_data(
            'read SKP_VERSION',
            stdout=api.raw_io.output('42')) +
        api.step_data(
            'read SK_IMAGE_VERSION',
            stdout=api.raw_io.output('42')) +
       api.step_data(
            'exists skia_dm',
            stdout=api.raw_io.output(''))
      )

    return test_data

  for mainname, subordinates in TEST_BUILDERS.iteritems():
    for subordinatename, builders_by_subordinate in subordinates.iteritems():
      for builder in builders_by_subordinate:
        test = (
          api.test(builder) +
          api.properties(buildername=builder,
                         mainname=mainname,
                         subordinatename=subordinatename,
                         buildnumber=5,
                         revision='abc123',
                         swarm_out_dir='[SWARM_OUT_DIR]') +
          api.path.exists(
              api.path['subordinate_build'].join('skia'),
              api.path['subordinate_build'].join('tmp', 'uninteresting_hashes.txt')
          )
        )
        if ('Android' in builder and
            ('Test' in builder or 'Perf' in builder) and
            not 'Appurify' in builder):
          test += AndroidTestData(builder)
        if 'Trybot' in builder:
          test += api.properties(issue=500,
                                 patchset=1,
                                 rietveld='https://codereview.chromium.org')
        if 'Win' in builder:
          test += api.platform('win', 64)


        yield test

