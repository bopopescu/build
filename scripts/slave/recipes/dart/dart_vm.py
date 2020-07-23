# Copyright 2015 The Chromium Authors. All rights reserved.
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

linux_clang_env = {'CC': 'third_party/clang/linux/bin/clang',
                   'CXX': 'third_party/clang/linux/bin/clang++'}
clang_asan = 'third_party/clang/linux/bin/clang++ -fsanitize=address -fPIC'
linux_asan_env = {
  'x64': {'CXX': clang_asan,
          'ASAN_OPTIONS': 'handle_segv=0:detect_stack_use_after_return=1'},
  'ia32': {'CXX': clang_asan,
           'ASAN_OPTIONS': 'handle_segv=0:detect_stack_use_after_return=0'},
}
windows_env = {'LOGONSERVER': '\\\\AD1'}
default_envs = {
  'linux': linux_clang_env,
  'mac': {},
  'win': windows_env,
}

builders = {
  # This is used by recipe coverage tests, not by any actual main.
  'test-coverage': {
    'mode': 'release',
    'target_arch': 'x64',
    'env': linux_clang_env,
    'clobber': True},
}

for platform in ['linux', 'mac', 'win']:
  for arch in ['x64', 'ia32']:
    for mode in ['debug', 'release']:
      builders['vm-%s-%s-%s' % (platform, mode, arch)] = {
        'mode': mode,
        'target_arch': arch,
        'env': default_envs[platform],
        'test_args': ['--exclude-suite=pkg'],
      }

for arch in ['simmips', 'simarm', 'simarm64']:
  for mode in ['debug', 'release']:
    builders['vm-linux-%s-%s' % (mode, arch)] = {
      'mode': mode,
      'target_arch': arch,
      'env': {},
      'test_args': ['--exclude-suite=pkg'],
    }

for arch in ['x64', 'ia32']:
  asan = builders['vm-linux-release-%s' % arch].copy()
  asan_args = ['--builder-tag=asan', '--timeout=240']
  asan_args.extend(asan['test_args'])
  asan['test_args'] = asan_args
  asan['env'] = linux_asan_env[arch]
  builders['vm-linux-release-%s-asan' % arch] = asan

  opt = builders['vm-linux-release-%s' % arch].copy()
  opt_args = ['--vm-options=--optimization-counter-threshold=5']
  opt_args.extend(opt['test_args'])
  opt['test_args'] = opt_args
  builders['vm-linux-release-%s-optcounter-threshold' % arch] = opt

builders['vm-win-debug-ia32-russian'] = builders['vm-win-debug-ia32']

def RunSteps(api):
  api.gclient.set_config('dart')
  api.path.c.dynamic_paths['tools'] = None
  api.bot_update.ensure_checkout(force=True)
  api.path['tools'] = api.path['checkout'].join('tools')
  buildername = api.properties.get('buildername')
  (buildername, _, channel) = buildername.rpartition('-')
  assert channel in ['be', 'dev', 'stable', 'integration']
  b = builders[buildername]


  if b.get('clobber', False):
      api.python('clobber',
                 api.path['tools'].join('clean_output_directory.py'),
                 cwd=api.path['checkout'])

  api.gclient.runhooks()

  api.python('taskkill before building',
             api.path['checkout'].join('tools', 'task_kill.py'),
             args=['--kill_browsers=True'],
             cwd=api.path['checkout'])

  build_args = ['-m%s' % b['mode'], '--arch=%s' % b['target_arch'], 'runtime']
  api.python('build dart',
             api.path['checkout'].join('tools', 'build.py'),
             args=build_args,
             cwd=api.path['checkout'],
             env=b['env'])

  with api.step.defer_results():
    test_args = ['-m%s' % b['mode'],
                 '--arch=%s' % b['target_arch'],
                 '--progress=line',
                 '--report',
                 '--time',
                 '--failure-summary',
                 '--write-debug-log',
                 '--write-test-outcome-log',
                 '--copy-coredumps']
    test_args.extend(b.get('test_args', []))
    api.python('vm tests',
               api.path['checkout'].join('tools', 'test.py'),
               args=test_args,
               cwd=api.path['checkout'])
    test_args.append('--checked')
    api.python('checked vm tests',
               api.path['checkout'].join('tools', 'test.py'),
               args=test_args,
               cwd=api.path['checkout'])
    # TODO(whesse): Add archive coredumps step from dart_factory.py.

    api.python('taskkill after testing',
               api.path['checkout'].join('tools', 'task_kill.py'),
               args=['--kill_browsers=True'],
               cwd=api.path['checkout'])

def GenTests(api):
   yield (
      api.test('vm-linux-release-x64-asan-be') + api.platform('linux', 64) +
      api.properties.generic(mainname='client.dart',
                             buildername='vm-linux-release-x64-asan-be'))
   yield (
      api.test('test-coverage') + api.platform('linux', 32) +
      api.properties.generic(mainname='client.dart',
                             buildername='test-coverage-be'))
