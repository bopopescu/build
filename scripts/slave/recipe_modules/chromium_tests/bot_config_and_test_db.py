# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import copy

from recipe_engine.types import freeze


MB_CONFIG_FILENAME = ['tools', 'mb', 'mb_config.pyl']


class BotConfig(object):
  """Wrapper that allows combining several compatible bot configs."""

  def __init__(self, bots_dict, bot_ids):
    self._bots_dict = bots_dict

    assert len(bot_ids) >= 1
    self._bot_ids = bot_ids

  def _consistent_get(self, getter, name, default=None):
    result = getter(self._bot_ids[0], name, default)
    for bot_id in self._bot_ids:
      other_result = getter(bot_id, name, default)
      assert result == other_result, (
          'Inconsistent value for %r: bot %r has %r, '
          'but bot %r has %r' % (
              name, self._bot_ids[0], result, bot_id, other_result))
    return result

  def _get_builder_bot_config(self, bot_id):
    # WARNING: This doesn't take into account dynamic
    # tests from test spec etc. If you need that, please use bot_db.
    return self._bots_dict.get(bot_id['mainname'], {}).get(
        'builders', {}).get(bot_id['buildername'], {})

  def _get(self, bot_id, name, default=None):
    return self._get_builder_bot_config(bot_id).get(name, default)

  def get(self, name, default=None):
    return self._consistent_get(self._get, name, default)

  def _get_main_setting(self, bot_id, name, default=None):
    return self._bots_dict.get(bot_id['mainname'], {}).get(
        'settings', {}).get(name, default)

  def get_main_setting(self, name, default=None):
    return self._consistent_get(self._get_main_setting, name, default)

  def _get_test_spec(self, chromium_tests_api, mainname):
    if len(self._bot_ids) == 1:
      bot_config = self._get_builder_bot_config(self._bot_ids[0])

      # The official builders specify the test spec using a test_spec property in
      # the bot_config instead of reading it from a file.
      if 'test_spec' in bot_config:
        return { self._bot_ids[0]['buildername']: bot_config['test_spec'] }

    test_spec_file = self.get('testing', {}).get(
        'test_spec_file', '%s.json' % mainname)

    # TODO(phajdan.jr): Bots should have no generators instead.
    if self.get('disable_tests'):
      return {}
    return chromium_tests_api.read_test_spec(chromium_tests_api.m, test_spec_file)

  def initialize_bot_db(self, chromium_tests_api, bot_db, bot_update_step):
    # TODO(phajdan.jr): Bots should have no generators instead.
    if self.get('disable_tests'):
      scripts_compile_targets = {}
    else:
      scripts_compile_targets = \
          chromium_tests_api.get_compile_targets_for_scripts().json.output

    mainnames = set(bot_id['mainname'] for bot_id in self._bot_ids)
    for mainname in mainnames:
      test_spec = self._get_test_spec(chromium_tests_api, mainname)

      # We manually thaw the path to the elements we are modifying, since the
      # builders are frozen.
      main_dict = dict(self._bots_dict[mainname])
      builders = main_dict['builders'] = dict(main_dict['builders'])
      for loop_buildername in builders:
        builder_dict = builders[loop_buildername] = (
            dict(builders[loop_buildername]))
        builders[loop_buildername]['tests'] = (
            chromium_tests_api.generate_tests_from_test_spec(
                chromium_tests_api.m, test_spec, builder_dict,
                loop_buildername, mainname,
                # TODO(phajdan.jr): Get enable_swarming value from builder_dict.
                # Above should remove the need to get bot_config and buildername
                # in this method.
                self.get('enable_swarming', False),
                builder_dict.get('swarming_dimensions', {}),
                scripts_compile_targets,
                builder_dict.get('test_generators', []),
                bot_update_step
            ))

      bot_db._add_main_dict_and_test_spec(
          mainname, freeze(main_dict), freeze(test_spec))

  def should_force_legacy_compiling(self, chromium_tests_api):
    """Determines if a given chromium revision needs to be built with gyp.

    This is done by checking the contents of tools/mb/mb_config.pyl at the rev.

    Returns:
      True if the revision occurred before the changeover from GYP to MP.
    """
    try:
      config_pyl = chromium_tests_api.m.file.read(
          'Reading MB config',
          chromium_tests_api.m.path['checkout'].join(*MB_CONFIG_FILENAME),
          test_data=('{\'mains\': {'
                     '\'tryserver.chromium.perf\': {'
                     '\'linux_perf_bisect_builder\':'
                     '\'gyp_something_something\'}}}'))
      config = ast.literal_eval(config_pyl or '{}')
      for bot_id in self._bot_ids:
        _ = config['mains'][bot_id['mainname']][bot_id['buildername']]
      result_text = 'MB is enabled for this builder at this revision.'
      log_name = 'Builder MB-ready'
      p = chromium_tests_api.m.step.active_result.presentation
      p.logs[log_name] = [result_text]
      return False
    except (chromium_tests_api.m.step.StepFailure, KeyError):
      result_text = 'MB is not enabled for this builder at this revision.'
      log_name = 'Builder NOT MB-ready'
      p = chromium_tests_api.m.step.active_result.presentation
      p.logs[log_name] = [result_text]
      p.status = chromium_tests_api.m.step.WARNING
      return True

  def get_tests(self, bot_db):
    tests = []
    for bot_id in self._bot_ids:
      bot_config = bot_db.get_bot_config(
          bot_id['mainname'], bot_id['buildername'])
      tests.extend([copy.deepcopy(t) for t in bot_config.get('tests', [])])

      if bot_id.get('tester'):
        bot_config = bot_db.get_bot_config(
            bot_id['mainname'], bot_id['tester'])
        tests.extend([copy.deepcopy(t) for t in bot_config.get('tests', [])])

    tests_including_triggered = list(tests)
    for bot_id in self._bot_ids:
      bot_config = bot_db.get_bot_config(
          bot_id['mainname'], bot_id['buildername'])

      for _, test_bot in bot_db.bot_configs_matching_parent_buildername(
          bot_id['mainname'], bot_id['buildername']):
        tests_including_triggered.extend(test_bot.get('tests', []))

    return tests, tests_including_triggered

  def get_compile_targets(self, chromium_tests_api, bot_db, tests):
    compile_targets = set()
    for bot_id in self._bot_ids:
      bot_config = bot_db.get_bot_config(
          bot_id['mainname'], bot_id['buildername'])
      compile_targets.update(set(bot_config.get('compile_targets', [])))
      compile_targets.update(bot_db.get_test_spec(
          bot_id['mainname'], bot_id['buildername']).get(
              'additional_compile_targets', []))

    if self.get('add_tests_as_compile_targets', True):
      for t in tests:
        compile_targets.update(t.compile_targets(chromium_tests_api.m))

    return sorted(compile_targets)

  def matches_any_bot_id(self, fun):
    return any(fun(bot_id) for bot_id in self._bot_ids)


class BotConfigAndTestDB(object):
  """An immutable database of bot configurations and test specifications.
  Holds the data for potentially multiple waterfalls (mainnames). Most
  queries against this database are made with (mainname, buildername)
  pairs.
  """

  def __init__(self):
    # Indexed by mainname. Each entry contains a main_dict and a
    # test_spec.
    self._db = {}

  def _add_main_dict_and_test_spec(self, mainname, main_dict, test_spec):
    """Only used during construction in chromium_tests.prepare_checkout. Do not
    call this externally.
    """
    # TODO(kbr): currently the main_dicts that are created by
    # get_main_dict_with_dynamic_tests are over-specialized to a
    # particular builder -- the "enable_swarming" flag paradoxically comes
    # from that builder, rather than from each individual builder and/or
    # the parent builder. This needs to be fixed so that there's exactly
    # one main_dict per waterfall.
    assert mainname not in self._db, (
        'Illegal attempt to add multiple main dictionaries for waterfall %s' %
        (mainname))
    self._db[mainname] = { 'main_dict': main_dict,
                             'test_spec': test_spec }

  def get_bot_config(self, mainname, buildername):
    return self._db[mainname]['main_dict'].get('builders', {}).get(
        buildername)

  def get_main_settings(self, mainname):
    return self._db[mainname]['main_dict'].get('settings', {})

  def bot_configs_matching_parent_buildername(
      self, mainname, parent_buildername):
    """A generator of all the (buildername, bot_config) tuples whose
    parent_buildername is the passed one on the given main.
    """
    for buildername, bot_config in self._db[mainname]['main_dict'].get(
        'builders', {}).iteritems():
      if bot_config.get('parent_buildername') == parent_buildername:
        yield buildername, bot_config

  def get_test_spec(self, mainname, buildername):
    return self._db[mainname]['test_spec'].get(buildername, {})
