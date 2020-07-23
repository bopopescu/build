# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Recipe module for Skia Swarming compile.


DEPS = [
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'skia',
]


TEST_BUILDERS = {
  'client.skia.compile': {
    'skiabot-linux-compile-000': [
      'Build-Mac-Clang-Arm7-Release-iOS',
      'Build-Ubuntu-GCC-Arm7-Debug-Android-Trybot',
      'Build-Ubuntu-GCC-Arm7-Release-Android',
    ],
    'skiabot-win-compile-000': [
      'Build-Win-MSVC-x86-Debug-VS2015',
    ],
  },
}


def RunSteps(api):
  api.skia.setup(running_in_swarming=True)
  api.skia.compile_steps()
  api.skia.cleanup_steps()


def GenTests(api):
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
        if 'Win' in builder:
          test += api.platform('win', 64)

        if 'Android' in builder:
          ccache = '/usr/bin/ccache' if 'Appurify' in builder else None
          test += api.step_data('has ccache?',
                                stdout=api.json.output({'ccache':ccache}))
        if 'Trybot' in builder:
          test += api.properties(issue=500,
                                 patchset=1,
                                 rietveld='https://codereview.chromium.org')

        yield test
