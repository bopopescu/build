# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'file',
  'gsutil',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
  'test_utils',
]

GCS_BUCKET = 'gs://dart-cross-compiled-binaries'

builders = {
  'target-arm-vm-linux-release': {
    'mode': 'release',
    'target_arch': 'arm'},
}

def tarball_name(arch, mode, revision):
  return 'cross_build_%s_%s_%s.tar.bz2' % (arch, mode, revision)

def RunSteps(api):
  api.gclient.set_config('dart')
  api.path.c.dynamic_paths['tools'] = None
  revision = api.properties['revision']
  api.bot_update.ensure_checkout(force=True)

  api.path['tools'] = api.path['checkout'].join('tools')
  buildername = api.properties.get('buildername')
  (buildername, _, channel) = buildername.rpartition('-')
  assert channel in ['be', 'dev', 'stable', 'integration']
  buildername = buildername.replace('-recipe', '')
  b = builders[buildername]

  api.python('clobber',
             api.path['tools'].join('clean_output_directory.py'),
             cwd=api.path['checkout'], ok_ret='any')
  api.gclient.runhooks()

  tarball = tarball_name(b['target_arch'], b['mode'], revision)
  uri = "%s/%s" % (GCS_BUCKET, tarball)
  api.gsutil(['cp', uri, tarball],
             name='download tarball',
             cwd=api.path['checkout'])
  api.step('untar tarball', ['tar', '-xjf', tarball], cwd=api.path['checkout'])

  with api.step.defer_results():
    test_args = ['--mode=%s' % b['mode'],
                 '--arch=%s' % b['target_arch'],
                 '--progress=line',
                 '--report',
                 '--time',
                 '--failure-summary',
                 '--write-debug-log',
                 '--write-test-outcome-log',
                 '--exclude-suite=pkg']
    test_args.extend(b.get('test_args', []))
    api.python('vm tests',
               api.path['tools'].join('test.py'),
               args=test_args,
               cwd=api.path['checkout'])
    test_args.extend(['--checked', '--append_logs'])
    api.python('checked vm tests',
               api.path['tools'].join('test.py'),
               args=test_args,
               cwd=api.path['checkout'])
    api.step('delete tarball',
             ['rm', tarball],
             cwd=api.path['checkout'])
    api.python('clobber',
               api.path['tools'].join('clean_output_directory.py'),
               cwd=api.path['checkout'])


def GenTests(api):
  yield (
    api.test('target-arm-vm-linux-release') +
    api.platform('linux', 64) +
    api.properties.generic(mainname='client.dart',
                           buildername='target-arm-vm-linux-release-be',
                           revision='abcd1234efef5656'))
