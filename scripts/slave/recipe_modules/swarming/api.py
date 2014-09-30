# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools

from slave import recipe_api


# Minimally supported version of swarming.py script (reported by --version).
MINIMAL_SWARMING_VERSION = (0, 4, 10)


# Platform name as provided by 'platform' module -> Swarming OS dimension.
PLATFORM_TO_OS_DIMENSION = {
  'mac': 'Mac',
  'linux': 'Linux',
  # Run on Win7 by default. CI recipe may override OS to be XP if necessary.
  'win': 'Windows-6.1',
}


# The goal here is to take ~5m of actual test run per shard, e.g. the 'RunTest'
# section in the logs, so that the trade-off of setup time overhead vs latency
# is reasonable. The overhead is in the 15~90s range, with the vast majority
# being downloading the executable files. While it can be lowered, it'll stay in
# the "few seconds" range due to the sheer size of the executables to map.
# Anything not listed defaults to 1 shard.
# TODO(vadimsh): Get rid of this. chromium_trybot.py recipe is reading sharding
# config from test spec in src/. Swarming canary builder should do the same.
TESTS_SHARDS = {
  'browser_tests': 5,
  'interactive_ui_tests': 3,
  'sync_integration_tests': 4,
  'unit_tests': 2,
}


class SwarmingApi(recipe_api.RecipeApi):
  """Recipe module to use swarming.py tool to run tasks on Swarming.

  General usage:
    1. Tweak default task parameters applied to all swarming tasks (such as
       task_os_dimension and task_priority). This step is optional.
    2. Isolate some test using 'isolate' recipe module. Get isolated hash as
       a result of that process.
    3. Create a task configuration using 'task(...)' method, providing
       isolated hash obtained previously.
    4. Tweak the task parameters. This step is optional.
    5. Launch the task on swarming by calling 'trigger(...)'.
    6. Continue doing useful work locally while the task is running concurrently
       on swarming.
    7. Wait for task to finish and collect its result (exit code, logs)
       by calling 'collect(...)'.

  See also example.py for concrete code.
  """

  def __init__(self, **kwargs):
    super(SwarmingApi, self).__init__(**kwargs)
    self._swarming_server = 'https://chromium-swarm.appspot.com'
    self._profile = False
    self._verbose = False
    self._task_os_dimension = None
    self._task_priority = 200
    self._pending_tasks = set()

  @property
  def swarming_server(self):
    """URL of Swarming server to use, default is a production one."""
    return self._swarming_server

  @swarming_server.setter
  def swarming_server(self, value):
    """Changes URL of Swarming server to use."""
    self._swarming_server = value

  @property
  def profile(self):
    """True to run tasks with Swarming profiling enabled."""
    return self._profile

  @profile.setter
  def profile(self, value):
    """Enables or disables Swarming profiling."""
    assert isinstance(value, bool)
    self._profile = value

  @property
  def verbose(self):
    """True to run swarming scripts with verbose output."""
    return self._verbose

  @verbose.setter
  def verbose(self, value):
    """Enables or disables verbose output in swarming scripts."""
    assert isinstance(value, bool)
    self._verbose = value

  @property
  def task_os_dimension(self):
    """Swarming OS dimension to run task on: Mac, Linux, Windows-6.1, etc.

    Used for tasks triggered in current recipe unless recipe itself overrides
    it on per-task basis.

    Default is derived from 'target_os' build property (if set) or OS of
    a machine that runs the recipe (if 'target_os' is not set).
    """
    if self._task_os_dimension is None:
      # 'target_os' is defined in builder/tester configuration (where 'tester'
      # is a bot that just triggers the tasks). In that case target_os may be
      # different from OS that recipe is running on, i.e. bot running recipe
      # on Linux may trigger tasks running on Windows.
      target_os = self.m.properties.get('target_os')
      if target_os:  # pragma: no cover
        platform = self.m.platform.normalize_platform_name(target_os)
      else:
        platform = self.m.platform.name
      self._task_os_dimension = self.platform_to_os_dimension(platform)
    return self._task_os_dimension

  @task_os_dimension.setter
  def task_os_dimension(self, value):  # pragma: no cover
    """Sets Swarming OS dimension to run task on by default."""
    self._task_os_dimension = value

  @property
  def task_priority(self):
    """Swarming task priority for tasks triggered from the recipe."""
    return self._task_priority

  @task_priority.setter
  def task_priority(self, value):
    """Sets swarming task priority for tasks triggered from the recipe."""
    assert 0 <= value <= 255
    self._task_priority = value

  @staticmethod
  def platform_to_os_dimension(platform):
    """Given a platform name returns swarming OS dimension that represents it.

    Platform name is usually provided by 'platform' recipe module, it's one
    of 'win', 'linux', 'mac'. This function returns more concrete Swarming OS
    dimension that represent this platform on Swarming by default. For example,
    currently 'win' is represented by Windows 7 Swarming slaves ('Windows-6.1'
    OS dimension).

    Recipes are free to use other OS dimension if there's a need for it. For
    example WinXP try bot recipe may explicitly specify 'Windows-5.1' dimension.
    """
    return PLATFORM_TO_OS_DIMENSION[platform]

  def task(self, title, isolated_hash,
           make_unique=False, shards=None, extra_args=None):
    """Returns SwarmingTask instance that represents some isolated test.

    It can be customized if necessary (see SwarmingTask class below). Pass it
    to 'trigger' to launch it on swarming. Later pass the same instance to
    'collect' to wait for the task to finish and fetch its results.

    Args:
      title: name of the test, used as part of a task ID, also used as a key
          in TESTS_SHARDS mapping.
      isolated_hash: hash of isolated test on isolate server, the test should
          be already isolated there, see 'isolate' recipe module.
      make_unique: if True, will ensure task is run even if given isolated_hash
          in given configuration was already tested. Does that by appending
          current timestamp to task ID.
      shards: if defined, the number of shards to use for the task. By default
          this value is either 1 or based on the title.
      extra_args: list of command line arguments to pass to isolated tasks.
    """
    return SwarmingTask(
        title=title,
        isolated_hash=isolated_hash,
        dimensions={'os': self.task_os_dimension},
        env={},
        priority=self.task_priority,
        shards=shards or TESTS_SHARDS.get(title, 1),
        builder=self.m.properties.get('buildername', 'local'),
        build_number=self.m.properties.get('buildnumber', 0),
        profile=self.profile,
        suffix='' if not make_unique else '/%d' % (self.m.time.time() * 1000),
        extra_args=extra_args,
        collect_step_builder=self._default_collect_step)

  def gtest_task(self, title, isolated_hash, make_unique=False, shards=None,
                 test_launcher_summary_output=None, extra_args=None):
    """Returns SwarmingTask instance that represents some isolated gtest.

    Swarming recipe module knows how collect and interpret JSON files with test
    execution summary produced by chromium test launcher. It will combine JSON
    results from multiple shards and place it in path provided by
    |test_launcher_summary_output| placeholder.

    For meaning of the rest of the arguments see 'task' method.
    """
    extra_args = list(extra_args or [])

    # Ensure --test-launcher-summary-output is not already passed. We are going
    # to overwrite it.
    bad_args = any(
        x.startswith('--test-launcher-summary-output=') for x in extra_args)
    if bad_args:  # pragma: no cover
      raise ValueError('--test-launcher-summary-output should not be used.')

    # Append it. output.json name is expected by collect_gtest_task.py.
    extra_args.append(
        '--test-launcher-summary-output=${ISOLATED_OUTDIR}/output.json')

    # Make a task, configure it to be collected through shim script.
    task = self.task(title, isolated_hash, make_unique, shards, extra_args)
    task.collect_step_builder = lambda *args, **kwargs: (
        self._gtest_collect_step(test_launcher_summary_output, *args, **kwargs))
    return task

  def check_client_version(self):
    """Yields steps to verify compatibility with swarming_client version."""
    return self.m.swarming_client.ensure_script_version(
        'swarming.py', MINIMAL_SWARMING_VERSION)

  def trigger(self, tasks, **kwargs):
    """Asynchronously launches a set of tasks on Swarming.

    This steps justs posts the tasks and immediately returns. Use 'collect' to
    wait for a task to finish and grab its result.

    Args:
      tasks: an enumerable of SwarmingTask instances.
      kwargs: passed to recipe step constructor as-is
    """
    # TODO(vadimsh): Trigger multiple tasks as a single step.
    assert all(isinstance(t, SwarmingTask) for t in tasks)
    results = []
    #TODO(martiniss) convert loop
    for task in tasks:
      assert task.task_name not in self._pending_tasks, (
          'Triggered same task twice: %s' % task.task_name)
      self._pending_tasks.add(task.task_name)

      # Trigger parameters.
      args = [
        'trigger',
        '--swarming', self.swarming_server,
        '--isolate-server', self.m.isolate.isolate_server,
        '--priority', str(task.priority),
        '--shards', str(task.shards),
        '--task-name', task.task_name,
        '--dump-json', self.m.json.output(),
      ]
      for name, value in sorted(task.dimensions.iteritems()):
        assert isinstance(value, basestring), value
        args.extend(['--dimension', name, value])
      for name, value in sorted(task.env.iteritems()):
        assert isinstance(value, basestring), value
        args.extend(['--env', name, value])
      if task.profile:
        args.append('--profile')
      if self.verbose:
        args.append('--verbose')

      # What isolated command to trigger.
      args.append(task.isolated_hash)

      # Additional command line args for isolated command.
      if task.extra_args:
        args.append('--')
        args.extend(task.extra_args)

      # Build corresponding step.
      step_result = self.m.python(
          name=self._get_step_name('trigger', task),
          script=self.m.swarming_client.path.join('swarming.py'),
          args=args,
          step_test_data=functools.partial(self._gen_trigger_step_data, task),
          **kwargs)
      self._trigger_followup(task, step_result)
      results.append(step_result)

    return results

  def collect(self, tasks, **kwargs):
    return list(self.collect_each(tasks, **kwargs))

  def collect_each(self, tasks, **kwargs):
    """Waits for a set of Swarming tasks to finish.

    Always waits for all task results. Failed tasks will be marked as such
    but would not abort the build.

    Args:
      tasks: an enumerable of SwarmingTask instances. All of them should have
          been triggered previously with 'trigger' method.
      kwargs: passed to recipe step constructor as-is
    """
    # TODO(vadimsh): Implement "wait for any" to wait for first finished task.
    # TODO(vadimsh): Update |tasks| in-place with results of task execution.
    # TODO(vadimsh): Add timeouts.
    assert all(isinstance(t, SwarmingTask) for t in tasks)
    #TODO(martiniss) convert loop
    for task in tasks:
      assert task.task_name in self._pending_tasks, (
          'Trying to collect a task that was not triggered: %s' %
          task.task_name)
      self._pending_tasks.remove(task.task_name)
      try:
        task.collect_step_builder(task, **kwargs)
      finally:
        step_result = self.m.step.active_result
        step_result.swarming_task = task
      try:
        json_data = step_result.json.output
        links = step_result.presentation.links
        for index, shard in enumerate(json_data['shards']):
          isolated_out = shard['isolated_out']
          link_name = 'shard #%d isolated out' % index
          links[link_name] = isolated_out['view_url']
      except (KeyError, AttributeError):
        # No isolated_out data exists (or any JSON at all)
        pass
      yield step_result

  def _default_collect_step(self, task, **kwargs):
    """Produces a step that collects a result of an arbitrary task."""
    # By default wait for all tasks to finish even if some of them failed.
    args = self._get_collect_cmd_args(task)
    args.extend(['--task-summary-json', self.m.json.output()])
    return self.m.python(
        name=self._get_step_name('', task),
        script=self.m.swarming_client.path.join('swarming.py'),
        args=args,
        step_test_data=functools.partial(self._gen_collect_step_data, task),
        **kwargs)

  def _gtest_collect_step(self, merged_test_output, task, **kwargs):
    """Produces a step that collects and processes a result of gtest task."""
    # By default wait for all tasks to finish even if some of them failed.
    # Shim script's own arguments.
    args = [
      '--swarming-client-dir', self.m.swarming_client.path,
      '--temp-root-dir', self.m.path['tmp_base'],
    ]

    # Where to put combined summary to, consumed by recipes. Also emit
    # test expectation only if |merged_test_output| is really used.
    step_test_data = None
    if merged_test_output:
      args.extend(['--merged-test-output', merged_test_output])
      step_test_data = lambda: self.m.json.test_api.canned_gtest_output(True)

    # Arguments for actual 'collect' command.
    args.append('--')
    args.extend(self._get_collect_cmd_args(task))

    # Always wait for all tasks to finish even if some of them failed. Allow
    # collect_gtest_task.py to emit all necessary annotations itself.
    return self.m.python(
        name=self._get_step_name('', task),
        script=self.resource('collect_gtest_task.py'),
        args=args,
        allow_subannotations=True,
        step_test_data=step_test_data,
        **kwargs)

  def _get_step_name(self, prefix, task):
    """SwarmingTask -> name of a step of a waterfall.

    Will take a task title (+ step name prefix) and optionally append
    OS dimension to it in case the task is triggered on OS that is different
    from OS this recipe is running on. It shortens step names for the most
    common case of triggering a task on the same OS as one that recipe
    is running on.

    Args:
      prefix: prefix to append to task title, like 'trigger'.
      task: SwarmingTask instance.

    Returns:
      '[<prefix>] <task title> (on <OS>)' where <OS> is optional.
    """
    prefix = '[%s] ' % prefix if prefix else ''

    # TODO(maruel): Differentiate Windows-6.1 from Windows-5.1, etc.
    task_os = task.dimensions['os']
    bot_os = self.platform_to_os_dimension(self.m.platform.name)
    suffix = '' if task_os == bot_os else ' on %s' % task_os

    return ''.join((prefix, task.title, suffix))

  def _get_collect_cmd_args(self, task):
    """SwarmingTask -> argument list for 'swarming.py' command."""
    args = [
      'collect',
      '--swarming', self.swarming_server,
      '--shards', str(task.shards),
      '--decorate',
      '--print-status-updates',
    ]
    if self.verbose:
      args.append('--verbose')
    args.append(task.task_name)
    return args

  def _gen_trigger_step_data(self, task):
    """Generates an expected value of --dump-json in 'trigger' step.

    Used when running recipes to generate test expectations.
    """
    # Suffixes of shard subtask names.
    subtasks = []
    if task.shards == 1:
      subtasks = ['']
    else:
      subtasks = [':%d:%d' % (task.shards, i) for i in range(task.shards)]
    return self.m.json.test_api.output({
      'base_task_name': task.task_name,
      'tasks': {
        '%s%s' % (task.task_name, suffix): {
          'task_id': '01%02d00' % i,
          'shard_index': i,
          'view_url': '%s/user/task/01%02d00' % (self.swarming_server, i),
        } for i, suffix in enumerate(subtasks)
      },
    })

  def _gen_collect_step_data(self, task):
    """Generates an expected value of --task-summary-json in 'collect' step.

    Used when running recipes to generate test expectations.
    """
    if task.shards == 1:
      subtasks = ['']
    else:
      subtasks = [':%d:%d' % (task.shards, i) for i in range(task.shards)]
    return self.m.json.test_api.output({
      'task_name': task.task_name,
      'shards': [
        {
          'isolated_out': {
              'view_url': 'blah',
          },
          'machine_id': 'fakemachine',
          'machine_tag': 'fakemachinetag',
        } for i, suffix in enumerate(subtasks)
      ],
    })

  def _trigger_followup(self, task, step_result):
    """Called as followup_fn for 'trigger' to add URLs to task shards."""
    # Store trigger output with the |task|, print links to triggered shards.
    if step_result.presentation != self.m.step.FAILURE:
      task._trigger_output = step_result.json.output
      links = step_result.presentation.links
      for index in xrange(task.shards):
        url = task.get_shard_view_url(index)
        if url:
          links['shard #%d' % index] = url

    assert not hasattr(step_result, 'swarming_task')
    step_result.swarming_task = task


class SwarmingTask(object):
  """Definition of a task to run on swarming."""

  def __init__(self, title, isolated_hash, dimensions, env, priority,
               shards, builder, build_number, profile, suffix, extra_args,
               collect_step_builder):
    """Configuration of a swarming task.

    Args:
      title: display name of the task, hints to what task is doing. Usually
          corresponds to a name of a test executable. Doesn't have to be unique.
      isolated_hash: hash of isolated file that describes all files needed to
          run the task as well as command line to launch. See 'isolate' recipe
          module.
      dimensions: key-value mapping with swarming dimensions that specify
          on what Swarming slaves task can run. One important dimension is 'OS',
          which defines platform flavor to run the task on.
      env: key-value mapping with additional environment variables to add to
          environment before launching the task executable.
      priority: integer [0, 1000] that defines how urgent the task is.
          Lower value corresponds to higher priority. Swarming service tries to
          execute tasks with higher priority first.
      shards: how many concurrent shards to run, makes sense only for
          isolated tests based on gtest. Swarming uses GTEST_SHARD_INDEX
          and GTEST_TOTAL_SHARDS environment variables to tell the executable
          what shard to run.
      builder: buildbot builder this task was triggered from.
      build_number: build number of a build this task was triggered from.
      profile: True to enable swarming profiling.
      suffix: string suffix to append to task ID.
      extra_args: list of command line arguments to pass to isolated tasks.
      collect_step_builder: callback that will be called to generate recipe step
          that collects and processes results of task execution, signature is
          collect_step_builder(task, **step_kwargs).
    """
    assert 'os' in dimensions
    self.title = title
    self.isolated_hash = isolated_hash
    self.dimensions = dimensions.copy()
    self.env = env.copy()
    self.priority = priority
    self.shards = shards
    self.builder = builder
    self.build_number = build_number
    self.profile = profile
    self.suffix = suffix
    self.extra_args = tuple(extra_args or [])
    self.collect_step_builder = collect_step_builder
    self._trigger_output = None

  @property
  def task_name(self):
    """Name of this task, derived from its other properties.

    Task ID identifies what task is doing and what machine configuration it
    expects. It is used as a key in table of a cached results. If Swarming
    service figures out that a task with given ID has successfully finished
    before, it will reuse the result right away, without even running
    the task again.
    """
    return '%s/%s/%s/%s/%d%s' % (
        self.title, self.dimensions['os'], self.isolated_hash,
        self.builder, self.build_number, self.suffix)

  def get_shard_view_url(self, index):
    """Returns URL of HTML page with shard details or None if not available.

    Works only after the task has been successfully triggered.
    """
    if self._trigger_output and self._trigger_output.get('tasks'):
      for shard_dict in self._trigger_output['tasks'].itervalues():
        if shard_dict['shard_index'] == index:
          return shard_dict['view_url']
