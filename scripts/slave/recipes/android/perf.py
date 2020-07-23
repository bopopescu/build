# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.types import freeze


DEPS = [
    'adb',
    'depot_tools/bot_update',
    'chromium',
    'chromium_android',
    'chromium_tests',
    'depot_tools/gclient',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
    'test_utils',
]


REPO_URL = 'https://chromium.googlesource.com/chromium/src.git'


def _ChromiumPerfTesters():
  def _AddTestSpec(name, perf_id, num_device_shards=1, num_host_shards=1,
                   target_bits=64, known_devices_file='.known_devices'):
    for shard_index in xrange(num_host_shards):
      builder_name = '%s (%d)' % (name, shard_index + 1)
      testers[builder_name] = _TestSpec(
          name, perf_id, num_device_shards, num_host_shards, shard_index,
          target_bits, known_devices_file)

  def _TestSpec(name, perf_id, num_device_shards, num_host_shards, shard_index,
                target_bits, known_devices_file):
    spec = {
      'perf_id': perf_id,
      'bucket': 'chrome-perf',
      'num_device_shards': num_device_shards,
      'num_host_shards': num_host_shards,
      'shard_index': shard_index,
      'test_spec_file': 'chromium.perf.json',
      'max_battery_temp': 350,
      'known_devices_file': known_devices_file,
    }

    if target_bits == 32:
      builder_name = 'android_perf_rel'
    elif target_bits == 64:
      builder_name = 'android_perf_rel_arm64'
      spec['recipe_config'] = 'tests_arm64'
    spec['path'] = lambda api: '%s/full-build-linux_%s.zip' % (
        builder_name, api.properties['parent_revision'])

    return spec

  testers = {}

  _AddTestSpec('Android Galaxy S5 Perf', 'android-galaxy-s5',
      num_device_shards=7, num_host_shards=3, target_bits=32)
  _AddTestSpec('Android Nexus5 Perf', 'android-nexus5',
      num_device_shards=7, num_host_shards=3, target_bits=32)
  _AddTestSpec('Android Nexus5X Perf', 'android-nexus5X',
      num_device_shards=7, num_host_shards=3)
  _AddTestSpec('Android Nexus6 Perf', 'android-nexus6',
      num_device_shards=7, num_host_shards=3, target_bits=32)
  _AddTestSpec('Android Nexus7v2 Perf', 'android-nexus7v2',
      num_device_shards=7, num_host_shards=3, target_bits=32)
  _AddTestSpec('Android Nexus9 Perf', 'android-nexus9',
      num_device_shards=7, num_host_shards=3)
  _AddTestSpec('Android One Perf', 'android-one',
      num_device_shards=7, num_host_shards=3, target_bits=32)

  return testers


BUILDERS = freeze({
  'chromium.perf': _ChromiumPerfTesters(),
  'client.v8.fyi': {
    'Android Nexus4 Perf': {
      'gclient_apply_config': [
        'v8_bleeding_edge_git',
        'chromium_lkcr',
        'show_v8_revision',
      ],
      'perf_id': 'v8-android-nexus4',
      'bucket': 'v8-android',
      'path': lambda api: ('v8_android_perf_rel/full-build-linux_%s.zip' %
                           api.properties['parent_revision']),
      'num_device_shards': 1,
      'set_component_rev': {'name': 'src/v8', 'rev_str': '%s'},
    },
  },
})


def RunSteps(api):
  mainname = api.properties['mainname']
  buildername = api.properties['buildername']
  # TODO(akuegel): Move the configs in builders.py in chromium_tests to this
  # recipe, and get rid of duplications.
  builder = dict(BUILDERS[mainname][buildername])
  builder_config = builder.get('recipe_config', 'base_config')
  kwargs = {
    'REPO_NAME':'src',
    'REPO_URL':REPO_URL,
    'INTERNAL':False,
    'BUILD_CONFIG':'Release',
    'TARGET_PLATFORM':'android',
  }

  api.chromium_android.set_config(builder_config, **kwargs)
  api.chromium.set_config(builder_config, **kwargs)
  api.gclient.set_config('perf')
  api.gclient.apply_config('android')
  for c in builder.get('gclient_apply_config', []):
    api.gclient.apply_config(c)

  if builder.get('set_component_rev'):
    # If this is a component build and the main revision is e.g. blink,
    # webrtc, or v8, the custom deps revision of this component must be
    # dynamically set to either:
    # (1) the revision of the builder,
    # (2) 'revision' from the waterfall, or
    # (3) 'HEAD' for forced builds with unspecified 'revision'.
    # TODO(machenbach): Use parent_got_cr_revision on testers with component
    # builds to match also the chromium revision from the builder.
    component_rev = api.properties.get(
        'parent_got_revision', api.properties.get('revision') or 'HEAD')
    dep = builder.get('set_component_rev')
    api.gclient.c.revisions[dep['name']] = dep['rev_str'] % component_rev

  bot_update_step = api.bot_update.ensure_checkout()

  test_spec_file = builder.get('test_spec_file')
  test_spec = {}
  if test_spec_file:
    test_spec = api.chromium_tests.read_test_spec(api, test_spec_file)

    scripts_compile_targets = \
        api.chromium_tests.get_compile_targets_for_scripts().json.output

    builder['tests'] = api.chromium_tests.generate_tests_from_test_spec(
        api, test_spec, builder, buildername, mainname, False, None,
        scripts_compile_targets, [api.chromium_tests.steps.generate_script],
        bot_update_step)

  api.path['checkout'] = api.path['subordinate_build'].join('src')
  api.chromium_android.clean_local_files()

  api.chromium_android.download_build(bucket=builder['bucket'],
    path=builder['path'](api))

  api.chromium_android.common_tests_setup_steps(perf_setup=True)

  api.chromium_android.adb_install_apk('ChromePublic.apk')

  test_runner = api.chromium_tests.create_test_runner(
      api, builder.get('tests', []))

  try:
    failures = []
    if test_runner:
      try:
        test_runner()
      except api.step.StepFailure as f:
        failures.append(f)

    dynamic_perf_tests = api.chromium_tests.steps.DynamicPerfTests(
        builder['perf_id'], 'android', None,
        max_battery_temp=builder.get('max_battery_temp'),
        num_device_shards=builder['num_device_shards'],
        num_host_shards=builder.get('num_host_shards', 1),
        shard_index=builder.get('shard_index', 0),
        known_devices_file=builder.get('known_devices_file', None))
    dynamic_perf_tests.run(api, None)

    if failures:
      raise api.step.StepFailure('src-side perf tests failed %s' % failures)
  finally:
    api.chromium_android.common_tests_final_steps(
        logcat_gs_bucket='chromium-android')


def _sanitize_nonalpha(text):
  return ''.join(c if c.isalnum() else '_' for c in text)


def GenTests(api):
  for mainname, builders in BUILDERS.iteritems():
    for buildername in builders:
      yield (
          api.test('full_%s_%s' % (_sanitize_nonalpha(mainname),
                                   _sanitize_nonalpha(buildername))) +
          api.properties.generic(
              repo_name='src',
              repo_url=REPO_URL,
              mainname=mainname,
              buildername=buildername,
              parent_buildername='parent_buildername',
              parent_buildnumber='1729',
              parent_revision='deadbeef',
              revision='deadbeef',
              subordinatename='subordinatename',
              target='Release'))
  yield (api.test('provision_devices') +
      api.properties.generic(
          repo_name='src',
              repo_url=REPO_URL,
              mainname='chromium.perf',
              buildername='Android Nexus5 Perf (1)',
              parent_buildername='parent_buildername',
              parent_buildnumber='1729',
              parent_revision='deadbeef',
              revision='deadbeef',
              subordinatename='subordinatename',
              target='Release')
      + api.step_data('provision_devices', retcode=1))
  yield (api.test('get_perf_test_list_old_data') +
      api.properties.generic(
          repo_name='src',
          repo_url=REPO_URL,
          mainname='chromium.perf',
          buildername='Android Nexus5 Perf (1)',
          parent_buildername='parent_buildername',
          parent_buildnumber='1729',
          parent_revision='deadbeef',
          revision='deadbeef',
          subordinatename='subordinatename',
          target='Release') +
      api.override_step_data(
        'get perf test list',
        api.json.output(['perf_test.foo', 'page_cycler.foo'])))
  yield (api.test('src_side_script_fails') +
      api.properties.generic(
          repo_name='src',
          repo_url=REPO_URL,
          mainname='chromium.perf',
          buildername='Android Nexus5 Perf (1)',
          parent_buildername='parent_buildername',
          parent_buildnumber='1729',
          parent_revision='deadbeef',
          revision='deadbeef',
          subordinatename='subordinatename',
          target='Release') +
      api.override_step_data(
        'read test spec',
        api.json.output({
            "Android Nexus5 Perf (1)": {
              "scripts": [
                {
                  "name": "host_info",
                  "script": "host_info.py"
                }]}})) +
      api.step_data('host_info', retcode=1))
  yield (api.test('test_failure') +
      api.properties.generic(
          repo_name='src',
          repo_url=REPO_URL,
          mainname='chromium.perf',
          buildername='Android Nexus5 Perf (1)',
          parent_buildername='parent_buildername',
          parent_buildnumber='1729',
          parent_revision='deadbeef',
          revision='deadbeef',
          subordinatename='subordinatename',
          target='Release') +
      api.override_step_data(
          'perf_test.foo', retcode=1))
  yield (api.test('missing_device') +
      api.properties.generic(
          repo_name='src',
          repo_url=REPO_URL,
          mainname='chromium.perf',
          buildername='Android Nexus5 Perf (1)',
          parent_buildername='parent_buildername',
          parent_buildnumber='1729',
          parent_revision='deadbeef',
          revision='deadbeef',
          subordinatename='subordinatename',
          target='Release') +
      api.override_step_data(
          'perf_test.foo', retcode=87))
