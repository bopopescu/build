# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from recipe_engine import recipe_api
from . import perf_test

BUCKET = 'chrome-perf'
RESULTS_GS_DIR = 'bisect-results'


class BisectTesterApi(recipe_api.RecipeApi):
  """A module for the bisect tester bot using the chromium recipe."""

  def __init__(self, **kwargs):
    super(BisectTesterApi, self).__init__(**kwargs)

  def local_test_enabled(self):
    buildername = os.environ.get('BUILDBOT_BUILDERNAME')
    cr_config = self.m.chromium.c
    if buildername and buildername.endswith('_bisect') and cr_config:
      return True # pragma: no cover
    return False

  def load_config_from_dict(self, bisect_config):
    """Copies the required configuration keys to a new dict."""
    return {
        'command': bisect_config['command'],
        'metric': bisect_config.get('metric'),
        'repeat_count': int(bisect_config.get('repeat_count', 20)),
        # The default is to NOT timeout, hence 0.
        'max_time_minutes': float(bisect_config.get('max_time_minutes', 0)),
        'test_type': bisect_config.get('test_type', 'perf')
    }

  def run_test(self, test_config, **kwargs):
    """Exposes perf tests implementation."""
    return perf_test.run_perf_test(self, test_config, **kwargs)

  def digest_run_results(self, run_results, retcodes, cfg):
    # TODO(qyearsley): Change this to not use cfg or retcodes and just
    # return values (or error) regardless of test_type.
    if not run_results or not retcodes:  # pragma: no cover
      return {'error': 'No values to aggregate.'}
    if cfg.get('test_type') == 'return_code':
      return {'values': retcodes}
    return {'values': run_results['measured_values']}

  def upload_results(self, output, results, retcodes, test_parameters):
    """Puts the results as a JSON file in a GS bucket."""
    job_name = (test_parameters.get('job_name') or
                self.m.properties.get('job_name'))
    gs_filename = '%s/%s.results' % (RESULTS_GS_DIR, job_name)
    contents = {'results': results, 'output': output, 'retcodes': retcodes}
    contents_json = json.dumps(contents)
    local_save_results = self.m.python('saving json to temp file',
                                       self.resource('put_temp.py'),
                                       stdout=self.m.raw_io.output(),
                                       stdin=self.m.raw_io.input(
                                           contents_json))
    local_file = local_save_results.stdout.splitlines()[0].strip()
    # TODO(robertocn): Look into using self.m.json.input(contents) instead of
    # local_file.
    self.m.gsutil.upload(local_file, BUCKET, gs_filename)

  def upload_job_url(self):
    """Puts the URL to the job's status on a GS file."""
    # If we are running the test locally there is no need for this.
    if self.local_test_enabled():
      return  # pragma: no cover
    gs_filename = RESULTS_GS_DIR + '/' + self.m.properties.get(
        'job_name')
    if 'TESTING_MASTER_HOST' in os.environ:  # pragma: no cover
      url = "http://%s:8041/json/builders/%s/builds/%s" % (
          os.environ['TESTING_MASTER_HOST'],
          self.m.properties['buildername'],
          self.m.properties['buildnumber'])
    else:
      url = "http://build.chromium.org/p/%s/json/builders/%s/builds/%s" % (
          self.m.properties['mainname'],
          self.m.properties['buildername'],
          self.m.properties['buildnumber'])
    local_save_results = self.m.python('saving url to temp file',
                                       self.resource('put_temp.py'),
                                       stdout=self.m.raw_io.output(),
                                       stdin=self.m.raw_io.input(url))
    local_file = local_save_results.stdout.splitlines()[0].strip()
    self.m.gsutil.upload(
        local_file, BUCKET, gs_filename, name=str(gs_filename))
