# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


DEPS = [
  'archive',
  'ct',
  'file',
  'perf_dashboard',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',
  'recipe_engine/time',
  'skia_swarming',
]


CT_PAGE_TYPE = '1k'
CT_BINARY = 'run_chromium_perf_swarming'
CT_ISOLATE = 'ct_top1k.isolate'

# Number of subordinates to shard CT runs to.
DEFAULT_CT_NUM_SLAVES = 100

# Only upload results to chromeperf if the number of reported webpages is equal
# to or more than the threshold.
NUM_WEBPAGES_REPORTED_THRESHOLD = 940


def _DownloadAndExtractBinary(api):
  """Downloads the binary from the revision passed to the recipe."""
  api.archive.download_and_unzip_build(
      step_name='Download and Extract Binary',
      target='Release',
      build_url=None,  # This is a required parameter, but has no effect.
      build_archive_url=api.properties['parent_build_archive_url'])


def _GetMainNameInPerfFormat(main_name):
  """Returns the main name in the capitalized format expected by chromeperf.

  Eg: chromium.perf.fyi becomes ChromiumPerfFyi.
  """
  return ''.join(x for x in main_name.title() if x != '.')


def RunSteps(api):
  # Figure out which benchmark to use.
  buildername = api.properties['buildername']
  if 'Repaint' in buildername:
    benchmark = 'repaint'
  elif 'RR' in buildername:
    benchmark = 'rasterize_and_record_micro'
  else:
    raise Exception('Do not recognise the buildername %s.' % buildername)

  # Checkout CT deps.
  api.ct.checkout_dependencies()
  # Setup swarming.
  api.skia_swarming.setup(api.path['checkout'].join('tools', 'luci-go'))

  # Download the prebuilt chromium binary.
  _DownloadAndExtractBinary(api)

  # Download Cluster Telemetry binary.
  api.ct.download_CT_binary(CT_BINARY)

  # Delete swarming_temp_dir to ensure it starts from a clean slate.
  api.file.rmtree('swarming temp dir', api.skia_swarming.swarming_temp_dir)

  ct_num_subordinates = api.properties.get('ct_num_subordinates', DEFAULT_CT_NUM_SLAVES)
  for subordinate_num in range(1, ct_num_subordinates + 1):
    # Download page sets and archives.
    api.ct.download_page_artifacts(CT_PAGE_TYPE, subordinate_num)

    # Create this subordinate's isolated.gen.json file to use for batcharchiving.
    isolate_dir = api.path['checkout'].join('chrome')
    isolate_path = isolate_dir.join(CT_ISOLATE)
    extra_variables = {
        'SLAVE_NUM': str(subordinate_num),
        'BENCHMARK': benchmark,
    }
    api.skia_swarming.create_isolated_gen_json(
        isolate_path, isolate_dir, 'linux', 'ct-%s' % subordinate_num,
        extra_variables)

  # Batcharchive everything on the isolate server for efficiency.
  tasks_to_swarm_hashes = api.skia_swarming.batcharchive(
      targets=['ct-%s' % num for num in range(1, ct_num_subordinates+1)])
  # Sort the list to go through tasks in order.
  tasks_to_swarm_hashes.sort()

  # Trigger all swarming tasks.
  tasks = api.skia_swarming.trigger_swarming_tasks(
      tasks_to_swarm_hashes,
      dimensions={'os': 'Ubuntu-14.04',
                  'gpu': '10de:104a',
                  'cpu': 'x86-64',
                  'pool': 'Chrome'})

  # The format of results_json is described in https://goo.gl/LmRBDk
  results_json = {
    'main': _GetMainNameInPerfFormat(api.properties['mainname']),
    'bot': api.properties['buildername'],
    'chart_data': {},
    'point_id': int(api.time.time()),
    'versions': {'chromium': api.properties['git_revision']},
    'supplemental': {},
  }

  # Now collect all tasks and populate results_json.
  subordinate_num = 0
  num_webpages_reported = 0
  for task in tasks:
    subordinate_num += 1
    api.skia_swarming.collect_swarming_task(task)

    output_dir = api.skia_swarming.tasks_output_dir.join(task.title).join('0')
    output_files = api.file.listdir('output dir', output_dir)
    if not output_files:
      raise api.step.StepFailure(
          'No output files were found for subordinate%d' % subordinate_num)
    subordinate_data_found = False

    # Loop through all output files and gather results in results_json.
    for json_output_file in output_files:
      json_output = api.json.read(
          'read output json', output_dir.join(json_output_file)).json.output
      if not json_output:
        # The output of some webpages could be empty if they repeatedly crashed.
        continue

      if not results_json['chart_data']:
        # Initialize the chart_data dict since it does not exist yet.
        results_json['chart_data'] = json_output
        # Empty out the 'summary' values of all fields because we will
        # recalculate them in the next section.
        results_json_charts = results_json['chart_data']['charts']
        for field_name in json_output['charts'].keys():
          results_json_charts[field_name]['summary']['values'] = []

      # The following block of code does the following:
      #
      # 1. Loop through all fields.
      #   2. Loop through all webpages in the field.
      #     3. Add the webpage to results_json_charts[field_name].
      #     4. Find all values of the webpage for this field.
      #     5. Calculate the average of webpage's values.
      #     6. Append the webpage's average to the 'summary' values of this
      #        field.
      #     7. Update the num_webpages_reported variable with the number of
      #        entries in the 'summary' values of this field.
      #
      # These steps are done to appropriately update the results_json dict with
      # new webpages.
      #
      results_json_charts = results_json['chart_data']['charts']
      # 1. Loop through all fields.
      for field_name in json_output['charts'].keys():
        subordinate_data_found = True
        # 2. Loop through all webpages in the field.
        for webpage_name in json_output['charts'][field_name].keys():
          if webpage_name == 'summary':
            # We will populate the summary section separately below.
            continue
          else:
            # 3. Add the webpage to results_json_charts[field_name].
            results_json_charts[field_name][webpage_name] = (
                json_output['charts'][field_name][webpage_name])
            # 4. Find all values of the webpage for this field.
            values = results_json_charts[field_name][webpage_name]['values']
            # 5. Calculate the average of webpage's values.
            values_avg = sum(values)/len(values)
            # 6. Append the webpage's average to the 'summary' values of this
            #    field.
            results_json_charts[field_name]['summary']['values'].append(
                values_avg)
            # 7. Update the num_webpages_reported variable with the number of
            #    entries in the 'summary' values of this field.
            num_webpages_reported = max(
                len(results_json_charts[field_name]['summary']['values']),
                num_webpages_reported)

    if not subordinate_data_found:
      # Throw a failure if this subordinate had no results.
      raise api.step.StepFailure('Received no data from subordinate #%d' % subordinate_num)

  # Add num_webpages_reported as a custom field to charts.
  results_json['chart_data']['charts']['num_webpages_reported'] = {
    'summary': {
      'important': True,
      'type': 'scalar',
      'name': 'num_webpages_reported',
      'std': 0.0,
      'units': 'num',
      'value': num_webpages_reported,
    }
  }

  # Upload results_json to the perf dashboard only if the number of reported
  # webpages matches the threshold.
  num_webpages_reported_threshold = api.properties.get(
      'num_webpages_reported_threshold', NUM_WEBPAGES_REPORTED_THRESHOLD)
  if num_webpages_reported >= num_webpages_reported_threshold:
    api.perf_dashboard.set_default_config()
    api.perf_dashboard.post(results_json)

  # Set build property that displays how many webpages reported results.
  api.step.active_result.presentation.properties['Number of webpages'] = (
      num_webpages_reported)


def _GetTestJsonOutput(webpage, values, populate_charts=True):
  json_output = {
    "trace_rerun_options": [],
    "format_version": "0.1",
    "benchmark_description": "Measures rasterize and record performance for "
                             "Cluster Telemetry.",
    "charts": {},
    "benchmark_metadata": {
      "rerun_options": [],
      "type": "telemetry_benchmark",
      "name": "rasterize_and_record_micro_ct",
      "description": "Measures rasterize and record performance for "
                     "Cluster Telemetry."
    },
    "next_version": "0.2",
    "benchmark_name": "rasterize_and_record_micro_ct"
  }

  if populate_charts:
    json_output['charts'] = {
      "viewport_picture_size": {
        webpage: {
          "std": 0.0,
          "name": "viewport_picture_size",
          "type": "list_of_scalar_values",
          "important": True,
          "values": values,
          "units": "bytes",
          "page_id": 0
        },
        "summary": {
          "std": 0.0,
          "name": "viewport_picture_size",
          "important": True,
          "values": values,
          "units": "bytes",
          "type": "list_of_scalar_values"
        }
      }
    }

  return json_output


def GenTests(api):
  mainname = 'chromium.perf.fyi'
  subordinatename = 'subordinate50-c1'
  parent_build_archive_url = 'http:/dummy-url.com'
  parent_got_swarming_client_revision = '12345'
  git_revision = 'xy12z43'
  ct_num_subordinates = 3
  num_webpages_reported_threshold = 3  # set threshold low for tests.

  # Subordinate1 file1 and file2.
  json_output_subordinate1_file1 = _GetTestJsonOutput('http://www.google.com',
                                                [20822, 20824])
  json_output_subordinate1_file2 = _GetTestJsonOutput('http://www.facebook.com',
                                                [208, 210])

  # Subordinate2 file1 and file2.
  json_output_subordinate2_file1 = _GetTestJsonOutput('http://www.amazon.com',
                                                [2, 4])
  json_output_subordinate2_file2 = _GetTestJsonOutput('http://www.twitter.com',
                                                [8, 10])

  # Subordinate3 file1 and file2.
  json_output_subordinate3_file1 = _GetTestJsonOutput('http://www.baidu.com',
                                                [20, 40])
  json_output_subordinate3_file2 = _GetTestJsonOutput('', [], populate_charts=False)

  yield(
    api.test('CT_Top1k_RR') +
    api.override_step_data(
        'read output json', api.json.output(json_output_subordinate1_file1)) +
    api.override_step_data(
        'read output json (2)', api.json.output(json_output_subordinate1_file2)) +
    api.override_step_data(
        'read output json (3)', api.json.output(json_output_subordinate2_file1)) +
    api.override_step_data(
        'read output json (4)', api.json.output(json_output_subordinate2_file2)) +
    api.override_step_data(
        'read output json (5)', api.json.output(json_output_subordinate3_file1)) +
    api.override_step_data(
        'read output json (6)', api.json.output(json_output_subordinate3_file2)) +
    api.properties(
        buildername='Linux CT Top1k RR Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    )
  )

  yield(
    api.test('CT_Top1k_Repaint') +
    api.override_step_data(
        'read output json', api.json.output(json_output_subordinate1_file1)) +
    api.override_step_data(
        'read output json (2)', api.json.output(json_output_subordinate1_file2)) +
    api.override_step_data(
        'read output json (3)', api.json.output(json_output_subordinate2_file1)) +
    api.override_step_data(
        'read output json (4)', api.json.output(json_output_subordinate2_file2)) +
    api.override_step_data(
        'read output json (5)', api.json.output(json_output_subordinate3_file1)) +
    api.override_step_data(
        'read output json (6)', api.json.output(json_output_subordinate3_file2)) +
    api.properties(
        buildername='Linux CT Top1k Repaint Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    )
  )

  yield(
    api.test('CT_Top1k_Unsupported') +
    api.properties(
        buildername='Linux CT Top1k Unsupported Perf',
        mainname=mainname,
        subordinatename=subordinatename,
         parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    ) +
    api.expect_exception('Exception')
  )

  yield(
    api.test('CT_Top1k_less_than_threshold') +
    api.override_step_data(
        'read output json', api.json.output(json_output_subordinate1_file1)) +
    api.override_step_data(
        'read output json (2)', api.json.output(json_output_subordinate1_file2)) +
    api.override_step_data(
        'read output json (3)', api.json.output(json_output_subordinate2_file1)) +
    api.override_step_data(
        'read output json (4)', api.json.output(json_output_subordinate2_file2)) +
    api.override_step_data(
        'read output json (5)', api.json.output(json_output_subordinate3_file1)) +
    api.override_step_data(
        'read output json (6)', api.json.output(json_output_subordinate3_file2)) +
    api.properties(
        buildername='Linux CT Top1k Repaint Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=6,
    )
  )

  yield(
    api.test('CT_Top1k_subordinate1_empty_dir') +
    api.override_step_data('listdir output dir', api.json.output([])) +
    api.properties(
        buildername='Linux CT Top1k Repaint Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    )
  )

  yield(
    api.test('CT_Top1k_subordinate2_no_output') +
    api.override_step_data(
        'read output json', api.json.output(json_output_subordinate1_file1)) +
    api.override_step_data(
        'read output json (2)', api.json.output(json_output_subordinate1_file2)) +
    api.properties(
        buildername='Linux CT Top1k Repaint Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    )
  )

  yield(
    api.test('CT_Top1k_subordinate2_failure') +
        api.override_step_data(
        'read output json', api.json.output(json_output_subordinate1_file1)) +
    api.override_step_data(
        'read output json (2)', api.json.output(json_output_subordinate1_file2)) +
    api.step_data('ct-2 on Ubuntu-14.04', retcode=1) +
    api.properties(
        buildername='Linux CT Top1k RR Perf',
        mainname=mainname,
        subordinatename=subordinatename,
        parent_build_archive_url=parent_build_archive_url,
        parent_got_swarming_client_revision=parent_got_swarming_client_revision,
        git_revision=git_revision,
        ct_num_subordinates=ct_num_subordinates,
        num_webpages_reported_threshold=num_webpages_reported_threshold,
    )
  )
