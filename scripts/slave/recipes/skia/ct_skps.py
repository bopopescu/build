# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.skia import global_constants


DEPS = [
  'ct',
  'file',
  'depot_tools/gclient',
  'gsutil',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',
  'recipe_engine/time',
  'skia',
  'skia_swarming',
  'swarming',
  'swarming_client',
  'depot_tools/tryserver',
]


CT_SKPS_ISOLATE = 'ct_skps.isolate'

# Do not batch archive more subordinates than this value. This is used to prevent
# no output timeouts in the 'isolate tests' step.
MAX_SLAVES_TO_BATCHARCHIVE = 100

# Number of subordinates to shard CT runs to.
DEFAULT_CT_NUM_SLAVES = 100

# The SKP repository to use.
DEFAULT_SKPS_CHROMIUM_BUILD = '57259e0-05dcb4c'


def RunSteps(api):
  # Figure out which repository to use.
  buildername = api.properties['buildername']
  if '10k' in buildername:
    ct_page_type = '10k'
  elif '1m' in buildername:
    ct_page_type = 'All'
  else:
    raise Exception('Do not recognise the buildername %s.' % buildername)

  # Figure out which configuration to build.
  if 'Release' in buildername:
    configuration = 'Release'
  else:
    configuration = 'Debug'

  # Figure out which tool to use.
  if 'DM' in buildername:
    skia_tool = 'dm'
  elif 'BENCH' in buildername:
    skia_tool = 'nanobench'
  else:
    raise Exception('Do not recognise the buildername %s.' % buildername)

  ct_num_subordinates = api.properties.get('ct_num_subordinates', DEFAULT_CT_NUM_SLAVES)

  # Optimize 10k DM runs by not sharding to 100 swarming bots. Shard to
  # only 1, sharding to more than that ends up taking more time due to overhead.
  if ct_page_type == '10k' and skia_tool == 'dm':
    ct_num_subordinates = 1
    ct_page_type = 'All'

  # Checkout Skia and Chromium.
  gclient_cfg = api.gclient.make_config()

  skia = gclient_cfg.solutions.add()
  skia.name = 'skia'
  skia.managed = False
  skia.url = global_constants.SKIA_REPO
  skia.revision = (api.properties.get('parent_got_revision') or
                   api.properties.get('orig_revision') or
                   api.properties.get('revision') or
                   'origin/main')
  gclient_cfg.got_revision_mapping['skia'] = 'got_revision'

  src = gclient_cfg.solutions.add()
  src.name = 'src'
  src.managed = False
  src.url = 'https://chromium.googlesource.com/chromium/src.git'
  src.revision = 'origin/main'  # Always checkout Chromium at ToT.

  for repo in (skia, src):
    api.skia.update_repo(repo)

  update_step = api.gclient.checkout(gclient_config=gclient_cfg)
  skia_hash = update_step.presentation.properties['got_revision']

  # Checkout Swarming scripts.
  # Explicitly set revision to empty string to checkout swarming ToT. If this is
  # not done then it crashes due to missing
  # api.properties['parent_got_swarming_client_revision'] which seems to be
  # set only for Chromium bots.
  api.swarming_client.checkout(revision='')
  # Ensure swarming_client is compatible with what recipes expect.
  api.swarming.check_client_version()
  # Setup Go isolate binary.
  chromium_checkout = api.path['subordinate_build'].join('src')
  api.skia_swarming.setup_go_isolate(chromium_checkout.join('tools', 'luci-go'))

  # Apply issue to the Skia checkout if this is a trybot run.
  api.tryserver.maybe_apply_issue()

  # Build the tool.
  api.step('build %s' % skia_tool,
           ['make', skia_tool, 'BUILDTYPE=%s' % configuration],
           cwd=api.path['checkout'])

  skps_chromium_build = api.properties.get(
      'skps_chromium_build', DEFAULT_SKPS_CHROMIUM_BUILD)

  # Set build property to make finding SKPs convenient.
  api.step.active_result.presentation.properties['Location of SKPs'] = (
      'https://pantheon.corp.google.com/storage/browser/%s/skps/%s/%s/' % (
          api.ct.CT_GS_BUCKET, ct_page_type, skps_chromium_build))

  # Delete swarming_temp_dir to ensure it starts from a clean slate.
  api.file.rmtree('swarming temp dir', api.skia_swarming.swarming_temp_dir)

  for subordinate_num in range(1, ct_num_subordinates + 1):
    # Download SKPs.
    api.ct.download_skps(
        ct_page_type, subordinate_num, skps_chromium_build,
        api.path['subordinate_build'].join('skps'))

    # Create this subordinate's isolated.gen.json file to use for batcharchiving.
    isolate_dir = chromium_checkout.join('chrome')
    isolate_path = isolate_dir.join(CT_SKPS_ISOLATE)
    extra_variables = {
        'SLAVE_NUM': str(subordinate_num),
        'TOOL_NAME': skia_tool,
        'GIT_HASH': skia_hash,
        'CONFIGURATION': configuration,
    }
    api.skia_swarming.create_isolated_gen_json(
        isolate_path, isolate_dir, 'linux', 'ct-%s-%s' % (skia_tool, subordinate_num),
        extra_variables)

  # Batcharchive everything on the isolate server for efficiency.
  max_subordinates_to_batcharchive = MAX_SLAVES_TO_BATCHARCHIVE
  if '1m' in buildername:
    # Break up the "isolate tests" step into batches with <100k files due to
    # https://github.com/luci/luci-go/issues/9
    max_subordinates_to_batcharchive = 5
  tasks_to_swarm_hashes = []
  for subordinate_start_num in xrange(1, ct_num_subordinates+1, max_subordinates_to_batcharchive):
    m = min(max_subordinates_to_batcharchive, ct_num_subordinates)
    batcharchive_output = api.skia_swarming.batcharchive(
        targets=['ct-' + skia_tool + '-%s' % num for num in range(
            subordinate_start_num, subordinate_start_num + m)])
    tasks_to_swarm_hashes.extend(batcharchive_output)
  # Sort the list to go through tasks in order.
  tasks_to_swarm_hashes.sort()

  # Trigger all swarming tasks.
  dimensions={'os': 'Ubuntu-14.04', 'cpu': 'x86-64', 'pool': 'Chrome'}
  if skia_tool == 'nanobench':
    # Run on GPU bots for nanobench.
    dimensions['gpu'] = '10de:104a'
  tasks = api.skia_swarming.trigger_swarming_tasks(
      tasks_to_swarm_hashes, dimensions=dimensions)

  # Now collect all tasks.
  failed_tasks = []
  for task in tasks:
    try:
      api.skia_swarming.collect_swarming_task(task)

      if skia_tool == 'nanobench':
        output_dir = api.skia_swarming.tasks_output_dir.join(
            task.title).join('0')
        utc = api.time.utcnow()
        gs_dest_dir = 'ct/%s/%d/%02d/%02d/%02d/' % (
            ct_page_type, utc.year, utc.month, utc.day, utc.hour)
        for json_output in api.file.listdir('output dir', output_dir):
          # TODO(rmistry): Use api.skia.gsutil_upload once the skia recipe
          #                is usable without needing to call gen_steps first.
          api.gsutil.upload(
              name='upload json output',
              source=output_dir.join(json_output),
              bucket='skia-perf',
              dest=gs_dest_dir,
              env={'AWS_CREDENTIAL_FILE': None, 'BOTO_CONFIG': None},
              args=['-R']
          )

    except api.step.StepFailure as e:
      failed_tasks.append(e)

  if failed_tasks:
    raise api.step.StepFailure(
        'Failed steps: %s' % ', '.join([f.name for f in failed_tasks]))


def GenTests(api):
  ct_num_subordinates = 5
  skia_revision = 'abc123'

  yield(
    api.test('CT_DM_10k_SKPs') +
    api.properties(
        buildername='Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_10k_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    )
  )

  yield(
    api.test('CT_BENCH_10k_SKPs') +
    api.properties(
        buildername=
            'Perf-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Release-CT_BENCH_10k_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    ) +
    api.path.exists(
        api.path['subordinate_build'].join('skia'),
        api.path['subordinate_build'].join('src')
    )
  )

  yield(
    api.test('CT_DM_1m_SKPs') +
    api.properties(
        buildername='Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_1m_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    )
  )

  yield (
    api.test('CT_DM_SKPs_UnknownBuilder') +
    api.properties(
        buildername=
            'Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_UnknownRepo_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    ) +
    api.expect_exception('Exception')
  )

  yield (
    api.test('CT_10k_SKPs_UnknownBuilder') +
    api.properties(
        buildername=
            'Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_UnknownTool_10k_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    ) +
    api.expect_exception('Exception')
  )

  yield(
    api.test('CT_DM_1m_SKPs_subordinate3_failure') +
    api.step_data('ct-dm-3 on Ubuntu-14.04', retcode=1) +
    api.properties(
        buildername='Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_1m_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    )
  )

  yield(
    api.test('CT_DM_1m_SKPs_2subordinates_failure') +
    api.step_data('ct-dm-1 on Ubuntu-14.04', retcode=1) +
    api.step_data('ct-dm-3 on Ubuntu-14.04', retcode=1) +
    api.properties(
        buildername='Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_1m_SKPs',
        ct_num_subordinates=ct_num_subordinates,
        revision=skia_revision,
    )
  )

  yield(
    api.test('CT_DM_10k_SKPs_Trybot') +
    api.properties(
        buildername=
            'Test-Ubuntu-GCC-GCE-CPU-AVX2-x86_64-Debug-CT_DM_10k_SKPs-Trybot',
        ct_num_subordinates=ct_num_subordinates,
        rietveld='codereview.chromium.org',
        issue=1499623002,
        patchset=1,
    )
  )
