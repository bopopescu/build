# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


# List of the benchmark that we run during the profiling step.
#
# TODO(sebmarchand): Move this into a BenchmarkSuite in telemetry, this way
# only have to run one benchmark.
_BENCHMARKS_TO_RUN = {
  'blink_perf.bindings',
  'blink_perf.canvas',
  'blink_perf.css',
  'blink_perf.dom',
  'blink_perf.events',
  'blink_perf.paint',
  'blink_perf.svg',
  'blink_style.top_25',
  'dromaeo.cssqueryjquery',
  'dromaeo.domcoreattr',
  'dromaeo.domcoremodify',
  'dromaeo.domcorequery',
  'dromaeo.domcoretraverse',
  'dromaeo.jslibattrprototype',
  'dromaeo.jslibeventprototype',
  'dromaeo.jslibmodifyprototype',
  'dromaeo.jslibstyleprototype',
  'dromaeo.jslibtraversejquery',
  'dromaeo.jslibtraverseprototype',
  'indexeddb_perf',
  'media.mse_cases',
  'octane',
  'page_cycler.morejs',
  'smoothness.top_25_smooth',
  'speedometer',
  'sunspider',
  'v8.infinite_scroll',
}


class PGOApi(recipe_api.RecipeApi):
  """
  PGOApi encapsulate the various step involved in a PGO build.
  """

  def __init__(self, **kwargs):
    super(PGOApi, self).__init__(**kwargs)

  def _compile_instrumented_image(self, bot_config):
    """
    Generates the instrumented version of the binaries.
    """
    self.m.chromium.set_config(bot_config['chromium_config_instrument'],
                               **bot_config.get('chromium_config_kwargs'))
    self.m.chromium.runhooks(name='Runhooks: Instrumentation phase.')
    # Remove the profile files from the previous builds.
    self.m.file.rmwildcard('*.pg[cd]', str(self.m.chromium.output_dir))
    self.m.chromium.compile(name='Compile: Instrumentation phase.',
                            force_clobber=bot_config.get('clobber', False))

  def _run_pgo_benchmarks(self):
    """
    Run a suite of telemetry benchmarks to generate some profiling data.
    """
    for benchmark in _BENCHMARKS_TO_RUN:
      try:
        args = [
            '--checkout-dir', self.m.path['checkout'],
            '--browser-type', self.m.chromium.c.build_config_fs.lower(),
            '--target-bits', self.m.chromium.c.TARGET_BITS,
            '--build-dir', self.m.chromium.output_dir,
            '--benchmark', benchmark,
        ]
        self.m.python(
          'Telemetry benchmark: %s' % benchmark,
          self.resource('run_benchmark.py'),
          args)
      except self.m.step.StepFailure:
        # Turn the failures into warning, we shouldn't stop the build for a
        # benchmark.
        step_result = self.m.step.active_result
        step_result.presentation.status = self.m.step.WARNING

  def _compile_optimized_image(self, bot_config):
    """
    Generates the optimized version of the binaries.
    """
    self.m.chromium.set_config(bot_config['chromium_config_optimize'],
                               **bot_config.get('chromium_config_kwargs'))
    self.m.chromium.runhooks(name='Runhooks: Optimization phase.')
    self.m.chromium.compile(name='Compile: Optimization phase.')

  def compile_pgo(self, bot_config):
    """
    Do a PGO build. This takes care of building an instrumented image, profiling
    it and then compiling the optimized version of it.
    """
    self.m.gclient.set_config(bot_config['gclient_config'])

    # Augment the solution if needed.
    self.m.gclient.c.solutions[0].url += bot_config.get('url_suffix', '')

    if self.m.properties.get('subordinatename') != 'fake_subordinate':
      self.m.chromium.taskkill()

    self.m.bot_update.ensure_checkout(force=True)
    if bot_config.get('patch_root'):
      self.m.path['checkout'] = self.m.path['subordinate_build'].join(
          bot_config.get('patch_root'))

    # First step: compilation of the instrumented build.
    self._compile_instrumented_image(bot_config)

    # Second step: profiling of the instrumented build.
    self._run_pgo_benchmarks()

    # Third step: Compilation of the optimized build, this will use the
    #     profile data files produced by the previous step.
    self._compile_optimized_image(bot_config)
