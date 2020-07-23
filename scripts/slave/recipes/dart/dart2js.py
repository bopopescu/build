# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'file',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
  'test_utils',
]


all_runtimes = ['d8', 'jsshell', 'ie9', 'ie10', 'ie11', 'ff',
            'safari', 'chrome', 'safarimobilesim', 'drt', 'chromeff',
            'ie10chrome', 'ie11ff']

multiple_runtimes = {'chromeff': ['chrome', 'ff'],
                     'ie10chrome': ['ie10', 'chrome'],
                     'ie11ff': ['ie11', 'ff']}
all_options = {'hostchecked': '--host-checked',
               'minified': '--minified',
               'cps': '--cps-ir',
               'csp': '--csp'}

IsFirstTestStep = True
def RunTests(api, test_args, test_specs, use_xvfb=False):
  for test_spec in test_specs:
    args = []
    args.extend(test_args)
    global IsFirstTestStep
    if IsFirstTestStep:
      IsFirstTestStep = False
    else:
      args.append('--append_logs')
    args.extend(test_spec['tests'])

    if use_xvfb:
      xvfb_cmd = ['xvfb-run', '-a', '--server-args=-screen 0 1024x768x24']
      xvfb_cmd.extend(['python', '-u', './tools/test.py'])
      xvfb_cmd.extend(args)
      api.step(test_spec['name'], xvfb_cmd, cwd=api.path['checkout'])
    else:
      api.python(test_spec['name'],
                 api.path['checkout'].join('tools', 'test.py'),
                 args=args,
                 cwd=api.path['checkout'])

def RunSteps(api):
  global IsFirstTestStep
  builder_name = str(api.properties.get('buildername')) # Convert from unicode.
  builder_fragments = builder_name.split('-')
  assert len(builder_fragments) > 3
  assert builder_fragments[0] == 'dart2js'
  system = builder_fragments[1]
  assert system in ['linux', 'mac10.11', 'win7', 'win8', 'win10']
  runtime = builder_fragments[2]
  assert runtime in all_runtimes
  channel = builder_fragments[-1]
  assert channel in ['be', 'dev', 'stable', 'integration']
  try:
    num_shards = int(builder_fragments[-2])
    shard = int(builder_fragments[-3])
    sharded = True
    options_end = - 3
  except ValueError:
    sharded = False
    options_end = - 1
  options = builder_fragments[3:options_end]
  for option in options:
    assert all_options.has_key(option)

  api.gclient.set_config('dart')
  api.path.c.dynamic_paths['tools'] = None
  api.bot_update.ensure_checkout(force=True)
  api.path['tools'] = api.path['checkout'].join('tools')

  api.gclient.runhooks()

  api.python('taskkill before building',
             api.path['checkout'].join('tools', 'task_kill.py'),
             args=['--kill_browsers=True'],
             cwd=api.path['checkout'])

  # If we ever build debug mode, use target dart2js_bot_debug, which skips try.
  build_args = ['-mrelease', '--arch=ia32', 'dart2js_bot']
  # TODO(whesse): Add env to step if needed.
  api.python('build dart',
             api.path['checkout'].join('tools', 'build.py'),
             args=build_args,
             cwd=api.path['checkout'])
  with api.step.defer_results():
    # Special hard-coded steps with compiler=none, run on selected runtimes
    if runtime == 'jsshell' and system == 'linux' and sharded:
      IsFirstTestStep = False
      api.python('dart2js unit tests',
                 api.path['checkout'].join('tools', 'test.py'),
                 args=["--mode=release", "--compiler=none", "--runtime=vm",
                       "--arch=ia32", "--time", "--use-sdk", "--report",
                       "--write-debug-log", "--write-test-outcome-log",
                       "--progress=buildbot", "-v", "--clear_browser_cache",
                       "--shards=%s" % num_shards, "--shard=%s" % shard,
                       "--checked", "dart2js", "try"],
                 cwd=api.path['checkout'])
    if runtime == 'drt':
      IsFirstTestStep = False
      args = ["--mode=release", "--compiler=none", "--runtime=drt",
              "--arch=ia32", "--time", "--use-sdk", "--report",
              "--write-debug-log", "--write-test-outcome-log",
              "--progress=buildbot", "-v", "--clear_browser_cache",
              "--checked", "try"]
      if sharded:
        args.extend(["--shards=%s" % num_shards, "--shard=%s" % shard])
      xvfb_cmd = ['xvfb-run', '-a', '--server-args=-screen 0 1024x768x24']
      xvfb_cmd.extend(['python', '-u', './tools/test.py'])
      xvfb_cmd.extend(args)
      api.step('none drt try tests', xvfb_cmd, cwd=api.path['checkout'])

    # Standard test steps, run on all runtimes.
    runtimes = multiple_runtimes.get(runtime, [runtime])
    for runtime in runtimes:
      # TODO(whesse): Call a script that prints the runtime version.
      test_args = ['--mode=release',
                   '--arch=ia32',
                   '--compiler=dart2js',
                   '--dart2js-batch',
                   '--runtime=%s' % runtime,
                   '--progress=buildbot',
                   '-v',
                   '--clear_browser_cache',
                   '--report',
                   '--time',
                   '--failure-summary',
                   '--write-debug-log',
                   '--write-test-outcome-log',
                   '--copy-coredumps']
      for option in options:
        test_args.append(all_options[option])
      if sharded:
        test_args.extend(['--shards=%s' % num_shards, '--shard=%s' % shard])

      if runtime in ['ie10', 'ie11']:
        test_args.append('--builder-tag=windows-%s' % runtime)
        test_specs = [{'name': 'dart2js %s tests' % runtime,
                  'tests': ['html', 'pkg', 'samples', 'co19']}]
      else:
        test_specs = [
          {'name': 'dart2js %s tests' % runtime, 'tests': []},
          {'name': 'dart2js %s extra tests' % runtime,
           'tests': ['dart2js_extra', 'dart2js_native']},
          {'name': 'dart2js %s try tests' % runtime, 'tests': ['try']}
        ]

      needs_xvfb = (runtime in ['drt', 'dartium', 'chrome', 'ff'] and
                    system == 'linux')
      RunTests(api, tuple(test_args), test_specs, use_xvfb=needs_xvfb)
      if runtime in ['d8', 'drt']:
        test_args.append('--checked')
        for spec in test_specs:
          spec['name'] = spec['name'].replace(' tests', ' checked tests')
        RunTests(api, tuple(test_args), test_specs, use_xvfb=needs_xvfb)

    # TODO(whesse): Add archive coredumps step from dart_factory.py.
    api.python('taskkill after testing',
               api.path['checkout'].join('tools', 'task_kill.py'),
               args=['--kill_browsers=True'],
               cwd=api.path['checkout'])
    # TODO(whesse): Upload the logs to cloud storage, put a link to them
    # in the step presentation.
    if system in ['linux', 'mac10.11']:
      api.step('debug log',
               ['cat', '.debug.log'],
               cwd=api.path['checkout'])

def GenTests(api):
   yield (
      api.test('dart2js-linux-jsshell-hostchecked-csp-3-5-be') +
      api.platform('linux', 64) +
      api.properties.generic(mainname='client.dart',
          buildername='dart2js-linux-jsshell-hostchecked-csp-3-5-be'))
   yield (
      api.test('dart2js-win7-ie10-dev') + api.platform('win', 32) +
      api.properties.generic(mainname='client.dart',
                             buildername='dart2js-win7-ie10-dev'))
   yield (
      api.test('dart2js-linux-drt-be') + api.platform('linux', 64) +
      api.properties.generic(mainname='client.dart',
                             buildername='dart2js-linux-drt-93-105-dev'))
