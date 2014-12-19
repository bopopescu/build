# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'chromium',
  'gclient',
  'gsutil',
  'json',
  'path',
  'properties',
  'python',
  'raw_io',
  'step',
]

CHROMIUM_GIT_URL = 'https://chromium.googlesource.com'

# Lists the additional repositories that should be checked out to be included
# in the source archive that is indexed by Codesearch.
ADDITIONAL_REPOS = {
  'infra': '%s/infra/infra' % CHROMIUM_GIT_URL,
  'tools/chrome-devtools-frontend':\
      '%s/chromium/tools/chrome-devtools-frontend' % CHROMIUM_GIT_URL,
  'tools/chromium-jobqueue':\
      '%s/chromium/tools/chromium-jobqueue' % CHROMIUM_GIT_URL,
  'tools/chromium-shortener':\
      '%s/chromium/tools/chromium-shortener' % CHROMIUM_GIT_URL,
  'tools/command_wrapper/bin':\
      '%s/chromium/tools/command_wrapper/bin' % CHROMIUM_GIT_URL,
  'tools/commit-queue': '%s/chromium/tools/commit-queue' % CHROMIUM_GIT_URL,
  'tools/depot_tools': '%s/chromium/tools/depot_tools' % CHROMIUM_GIT_URL,
  'tools/deps2git': '%s/chromium/tools/deps2git' % CHROMIUM_GIT_URL,
  'tools/gsd_generate_index':\
      '%s/chromium/tools/gsd_generate_index' % CHROMIUM_GIT_URL,
  'tools/perf': '%s/chromium/tools/perf' % CHROMIUM_GIT_URL,
}

SPEC = {
  # The builders have the following parameters:
  # - chromium_config_kwargs: parameters for the config of the chromium module.
  # - chromium_runhooks_kwargs: parameters for the runhooks step.
  # - compile_targets: the compile targets
  # - package_filename: The prefix of the name of the source archive.
  'builders': {
    'Chromium Linux Codesearch': {
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
      },
      'compile_targets': [
        'all',
      ],
      'environment': 'prod',
      'package_filename': 'chromium-src',
    },
    'ChromiumOS Codesearch': {
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_PLATFORM': 'chromeos',
      },
      'compile_targets': [
        'all',
      ],
      'environment': 'prod',
      'package_filename': 'chromiumos-src',
    },
    'Chromium Linux Codesearch Staging': {
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
      },
      'compile_targets': [
        'all',
      ],
      'environment': 'staging',
      'package_filename': 'chromium-src',
    },
    'ChromiumOS Codesearch Staging': {
      'chromium_config_kwargs': {
        'BUILD_CONFIG': 'Debug',
        'TARGET_PLATFORM': 'chromeos',
      },
      'compile_targets': [
        'all',
      ],
      'environment': 'staging',
      'package_filename': 'chromiumos-src',
    },
  },
}


def GenSteps(api):
  buildername = api.properties.get('buildername')

  bot_config = SPEC.get('builders', {}).get(buildername)

  # Checkout the repositories that are either directly needed or should be
  # included in the source archive.
  gclient_config = api.gclient.make_config('chromium')
  solution = gclient_config.solutions.add()
  solution.name = 'clang_indexer'
  solution.url = \
      'https://chrome-internal.googlesource.com/chrome/tools/clang_indexer'
  for name, url in ADDITIONAL_REPOS.iteritems():
    solution = gclient_config.solutions.add()
    solution.name = name
    solution.url = url
  api.gclient.c = gclient_config
  update_step = api.bot_update.ensure_checkout()
  api.chromium.set_build_properties(update_step.json.output['properties'])

  # Compile the code using clang.
  api.chromium.set_config('codesearch',
                          **bot_config.get('chromium_config_kwargs', {}))
  api.chromium.runhooks()
  targets = bot_config.get('compile_targets', [])
  debug_path = api.path['checkout'].join('out', api.chromium.c.BUILD_CONFIG)
  command = ['ninja', '-C', debug_path] + targets
  # Add the parameters for creating the compilation database.
  command += ['-t', 'compdb', 'cc', 'cxx', 'objc', 'objcxx']
  result = api.step('generate compilation database', command,
                    stdout=api.raw_io.output())
  # Upload the result to google storage (it might be needed for debugging).
  api.gsutil.upload(api.raw_io.input(data=result.stdout),
                    'chromium-browser-csindex',
                    api.path.join('json', 'compile_commands.json'))
  # Now compile the code for real.
  api.chromium.compile(targets, force_clobber=True)

  # Run the package_source.py script that creates and uploads the source archive
  # which also includes the .index files generated by the clang_indexer. The
  # script inspects factory properties, so the options are provided in this
  # format.
  fake_factory_properties = {
      'package_filename': bot_config.get('package_filename', ''),
  }
  args = [
      '--build-properties', api.json.dumps(api.chromium.build_properties),
      '--factory-properties', api.json.dumps(fake_factory_properties),
      '--path-to-compdb', api.raw_io.input(data=result.stdout),
      '--environment', bot_config.get('environment', ''),
  ]
  api.python('package_source',
             api.path['build'].join('scripts', 'slave', 'chromium',
                                    'package_source.py'),
             args)


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  for buildername, _ in SPEC['builders'].iteritems():
    test = (
      api.test('full_%s' % (_sanitize_nonalpha(buildername))) +
      api.step_data('generate compilation database',
                    stdout=api.raw_io.output('some compilation data')) +
      api.properties.generic(buildername=buildername, mastername='chromium.fyi')
    )

    yield test
