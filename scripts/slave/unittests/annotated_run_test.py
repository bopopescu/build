#!/usr/bin/env python

# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests that the tools/build annotated_run wrapper actually runs."""

import collections
import contextlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest

import test_env  # pylint: disable=W0403,W0611

import mock
from common import chromium_utils
from common import env
from subordinate import annotated_run
from subordinate import gce
from subordinate import infra_platform

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


MockOptions = collections.namedtuple('MockOptions',
    ('dry_run', 'logdog_force', 'logdog_butler_path', 'logdog_annotee_path',
     'logdog_verbose', 'logdog_service_account_json', 'logdog_pubsub_topic',
     'logdog_host'))


class AnnotatedRunTest(unittest.TestCase):
  def test_example(self):
    build_properties = {
      'recipe': 'annotated_run_test',
      'true_prop': True,
      'num_prop': 123,
      'string_prop': '321',
      'dict_prop': {'foo': 'bar'},
    }

    script_path = os.path.join(BASE_DIR, 'annotated_run.py')
    exit_code = subprocess.call([
        'python', script_path,
        '--build-properties=%s' % json.dumps(build_properties)])
    self.assertEqual(exit_code, 0)

  @mock.patch('subordinate.annotated_run._run_command')
  @mock.patch('subordinate.annotated_run.main')
  @mock.patch('sys.platform', return_value='win')
  @mock.patch('tempfile.mkstemp', side_effect=Exception('failure'))
  @mock.patch('os.environ', {})
  def test_update_scripts_must_run(self, _tempfile_mkstemp, _sys_platform,
                                   main, run_command):
    annotated_run.main.side_effect = Exception('Test error!')
    annotated_run._run_command.return_value = (0, "")
    annotated_run.shell_main(['annotated_run.py', 'foo'])

    gclient_path = os.path.join(env.Build, os.pardir, 'depot_tools',
                                'gclient.bat')
    run_command.assert_has_calls([
        mock.call([gclient_path, 'sync', '--force', '--verbose', '--jobs=2',
                   '--break_repo_locks'],
                  cwd=env.Build),
        mock.call([sys.executable, 'annotated_run.py', 'foo']),
        ])
    main.assert_not_called()


class _AnnotatedRunExecTestBase(unittest.TestCase):
  def setUp(self):
    logging.basicConfig(level=logging.ERROR+1)

    self.maxDiff = None
    self._patchers = []
    map(self._patch, (
        mock.patch('subordinate.annotated_run._run_command'),
        mock.patch('subordinate.infra_platform.get'),
        mock.patch('os.path.exists'),
        mock.patch('os.getcwd'),
        mock.patch('os.environ', {}),
        ))

    self.rt = annotated_run.Runtime()
    self.basedir = self.rt.tempdir()
    self.tdir = self.rt.tempdir()
    self.opts = MockOptions(
        dry_run=False,
        logdog_force=False,
        logdog_annotee_path=None,
        logdog_butler_path=None,
        logdog_verbose=False,
        logdog_service_account_json=None,
        logdog_pubsub_topic=None,
        logdog_host=None)
    self.properties = {
      'recipe': 'example/recipe',
      'mainname': 'main.random',
      'buildername': 'builder',
    }
    self.cwd = os.path.join('home', 'user')
    self.rpy_path = os.path.join(env.Build, 'scripts', 'subordinate', 'recipes.py')
    self.recipe_args = [
        sys.executable, '-u', self.rpy_path, '--verbose', 'run',
        '--workdir=%s' % (self.cwd,),
        '--properties-file=%s' % (self._tp('recipe_properties.json'),),
        'example/recipe']

    # Use public recipes.py path.
    os.getcwd.return_value = self.cwd
    os.path.exists.return_value = False

    # Pretend we're 64-bit Linux by default.
    infra_platform.get.return_value = ('linux', 64)

  def tearDown(self):
    self.rt.close()
    for p in reversed(self._patchers):
      p.stop()

  def _bp(self, *p):
    return os.path.join(*((self.basedir,) + p))

  def _tp(self, *p):
    return os.path.join(*((self.tdir,) + p))

  def _patch(self, patcher):
    self._patchers.append(patcher)
    patcher.start()
    return patcher

  def _config(self):
    return annotated_run.get_config()

  def _assertRecipeProperties(self, value):
    # Double-translate "value", since JSON converts strings to unicode.
    value = json.loads(json.dumps(value))
    with open(self._tp('recipe_properties.json')) as fd:
      self.assertEqual(json.load(fd), value)


class AnnotatedRunExecTest(_AnnotatedRunExecTestBase):

  def test_exec_successful(self):
    annotated_run._run_command.return_value = (0, '')

    rv = annotated_run._exec_recipe(self.rt, self.opts, self.basedir, self.tdir,
                                    self._config(), self.properties)
    self.assertEqual(rv, 0)
    self._assertRecipeProperties(self.properties)

    annotated_run._run_command.assert_called_once_with(self.recipe_args,
                                                       dry_run=False)


class AnnotatedRunLogDogExecTest(_AnnotatedRunExecTestBase):

  def setUp(self):
    super(AnnotatedRunLogDogExecTest, self).setUp()
    self._orig_whitelist = annotated_run.LOGDOG_WHITELIST_MASTER_BUILDERS
    annotated_run.LOGDOG_WHITELIST_MASTER_BUILDERS = {
      'main.some': [
        'yesbuilder',
      ],

      'main.all': [
        annotated_run.WHITELIST_ALL,
        'blacklisted',
      ],
    }
    self.properties.update({
      'mainname': 'main.some',
      'buildername': 'nobuilder',
      'buildnumber': 1337,
    })
    self.is_gce = False

    def is_gce():
      return self.is_gce
    is_gce_patch = mock.patch('subordinate.gce.Authenticator.is_gce',
                              side_effect=is_gce)
    is_gce_patch.start()
    self._patchers.append(is_gce_patch)

  def tearDown(self):
    annotated_run.LOGDOG_WHITELIST_MASTER_BUILDERS = self._orig_whitelist
    super(AnnotatedRunLogDogExecTest, self).tearDown()

  def _assertAnnoteeCommand(self, value):
    # Double-translate "value", since JSON converts strings to unicode.
    value = json.loads(json.dumps(value))
    with open(self._tp('logdog_annotee_cmd.json')) as fd:
      self.assertEqual(json.load(fd), value)

  def test_should_run_logdog(self):
    self.assertFalse(annotated_run._should_run_logdog({
      'mainname': 'main.undefined', 'buildername': 'any'}))
    self.assertFalse(annotated_run._should_run_logdog({
      'mainname': 'main.some', 'buildername': 'nobuilder'}))
    self.assertTrue(annotated_run._should_run_logdog({
      'mainname': 'main.some', 'buildername': 'yesbuilder'}))
    self.assertTrue(annotated_run._should_run_logdog({
      'mainname': 'main.all', 'buildername': 'anybuilder'}))
    self.assertFalse(annotated_run._should_run_logdog({
      'mainname': 'main.all', 'buildername': 'blacklisted'}))

  @mock.patch('os.path.isfile')
  @mock.patch('subordinate.annotated_run._get_service_account_json')
  def test_exec_with_whitelist_builder_runs_logdog(self, service_account,
                                                   isfile):
    self.properties['buildername'] = 'yesbuilder'

    isfile.return_value = True
    butler_path = self._bp('.recipe_logdog_cipd', 'logdog_butler')
    annotee_path = self._bp('.recipe_logdog_cipd', 'logdog_annotee')
    service_account.return_value = 'creds.json'
    annotated_run._run_command.return_value = (0, '')

    self._patch(mock.patch('tempfile.mkdtemp', return_value='foo'))
    config = self._config()
    rv = annotated_run._exec_recipe(self.rt, self.opts, self.basedir, self.tdir,
                                    config, self.properties)
    self.assertEqual(rv, 0)

    streamserver_uri = 'unix:%s' % (os.path.join('foo', 'butler.sock'),)
    service_account.assert_called_once_with(
        self.opts, config.logdog_platform.credential_path)
    annotated_run._run_command.assert_called_with(
        [butler_path,
            '-log-level', 'warning',
            '-prefix', 'bb/main.some/yesbuilder/1337',
            '-output', 'pubsub,topic="projects/luci-logdog/topics/logs"',
            '-service-account-json', 'creds.json',
            '-output-max-buffer-age', '15s',
            'run',
            '-stdout', 'tee=stdout',
            '-stderr', 'tee=stderr',
            '-streamserver-uri', streamserver_uri,
            '--',
            annotee_path,
                '-log-level', 'warning',
                '-butler-stream-server', streamserver_uri,
                '-logdog-host', 'luci-logdog',
                '-annotate', 'tee',
                '-name-base', 'recipes',
                '-print-summary',
                '-tee',
                '-json-args-path', self._tp('logdog_annotee_cmd.json'),
        ],
        dry_run=False)
    self._assertRecipeProperties(self.properties)
    self._assertAnnoteeCommand(self.recipe_args)

  @mock.patch('subordinate.annotated_run._logdog_bootstrap', return_value=0)
  def test_runs_bootstrap_when_forced(self, lb):
    opts = self.opts._replace(logdog_force=True)
    rv = annotated_run._exec_recipe(self.rt, opts, self.basedir, self.tdir,
                                    self._config(), self.properties)
    self.assertEqual(rv, 0)
    lb.assert_called_once()
    annotated_run._run_command.assert_called_once()

  @mock.patch('subordinate.annotated_run._logdog_bootstrap', return_value=2)
  def test_forwards_error_code(self, lb):
    opts = self.opts._replace(
        logdog_force=True)
    rv = annotated_run._exec_recipe(self.rt, opts, self.basedir, self.tdir,
                                    self._config(), self.properties)
    self.assertEqual(rv, 2)
    lb.assert_called_once()

  @mock.patch('subordinate.annotated_run._logdog_bootstrap',
              side_effect=Exception('Unhandled situation.'))
  def test_runs_directly_if_bootstrap_fails(self, lb):
    annotated_run._run_command.return_value = (123, '')

    rv = annotated_run._exec_recipe(self.rt, self.opts, self.basedir, self.tdir,
                                    self._config(), self.properties)
    self.assertEqual(rv, 123)

    lb.assert_called_once()
    annotated_run._run_command.assert_called_once_with(self.recipe_args,
                                                       dry_run=False)

  @mock.patch('os.path.isfile')
  @mock.patch('subordinate.annotated_run._logdog_install_cipd')
  @mock.patch('subordinate.annotated_run._get_service_account_json')
  def test_runs_directly_if_logdog_error(self, service_account, cipd, isfile):
    self.properties['buildername'] = 'yesbuilder'

    # Test Windows builder this time.
    infra_platform.get.return_value = ('win', 64)

    isfile.return_value = True
    cipd.return_value = ('logdog_butler.exe', 'logdog_annotee.exe')
    service_account.return_value = 'creds.json'
    def error_for_logdog(args, **kw):
      if len(args) > 0 and args[0] == 'logdog_butler.exe':
        return (250, '')
      return (4, '')
    annotated_run._run_command.side_effect = error_for_logdog

    config = self._config()

    self._patch(mock.patch('tempfile.mkdtemp', return_value='foo'))
    rv = annotated_run._exec_recipe(self.rt, self.opts, self.basedir, self.tdir,
                                    config, self.properties)
    self.assertEqual(rv, 4)

    streamserver_uri = 'net.pipe:LUCILogDogButler'
    service_account.assert_called_once_with(
        self.opts, config.logdog_platform.credential_path)
    annotated_run._run_command.assert_has_calls([
        mock.call([
            'logdog_butler.exe',
            '-log-level', 'warning',
            '-prefix', 'bb/main.some/yesbuilder/1337',
            '-output', 'pubsub,topic="projects/luci-logdog/topics/logs"',
            '-service-account-json', 'creds.json',
            '-output-max-buffer-age', '15s',
            'run',
            '-stdout', 'tee=stdout',
            '-stderr', 'tee=stderr',
            '-streamserver-uri', streamserver_uri,
            '--',
            'logdog_annotee.exe',
                '-log-level', 'warning',
                '-butler-stream-server', streamserver_uri,
                '-logdog-host', 'luci-logdog',
                '-annotate', 'tee',
                '-name-base', 'recipes',
                '-print-summary',
                '-tee',
                '-json-args-path', self._tp('logdog_annotee_cmd.json'),
        ], dry_run=False),
        mock.call(self.recipe_args, dry_run=False),
    ])

  @mock.patch('os.path.isfile')
  def test_can_find_credentials(self, isfile):
    isfile.return_value = True

    service_account_json = annotated_run._get_service_account_json(
        self.opts, 'creds.json')
    self.assertEqual(service_account_json, 'creds.json')

  def test_uses_no_credentials_on_gce(self):
    self.is_gce = True
    service_account_json = annotated_run._get_service_account_json(
        self.opts, ('foo', 'bar'))
    self.assertIsNone(service_account_json)

  def test_cipd_install(self):
    annotated_run._run_command.return_value = (0, '')

    pkgs = annotated_run._logdog_install_cipd(self.basedir,
        annotated_run.CipdBinary('infra/foo', 'v0', 'foo'),
        annotated_run.CipdBinary('infra/bar', 'v1', 'baz'),
        )
    self.assertEqual(pkgs, (self._bp('foo'), self._bp('baz')))

    annotated_run._run_command.assert_called_once_with([
      sys.executable,
       os.path.join(env.Build, 'scripts', 'subordinate', 'cipd.py'),
       '--dest-directory', self.basedir,
       '--json-output', os.path.join(self.basedir, 'packages.json'),
       '-P', 'infra/foo@v0',
       '-P', 'infra/bar@v1',
    ])

  def test_cipd_install_failure_raises_bootstrap_error(self):
    annotated_run._run_command.return_value = (1, '')

    self.assertRaises(annotated_run.LogDogBootstrapError,
        annotated_run._logdog_install_cipd,
        self.basedir,
        annotated_run.CipdBinary('infra/foo', 'v0', 'foo'),
        annotated_run.CipdBinary('infra/bar', 'v1', 'baz'),
    )

  def test_will_not_bootstrap_if_recursive(self):
    os.environ['LOGDOG_STREAM_PREFIX'] = 'foo'
    self.assertRaises(annotated_run.LogDogNotBootstrapped,
        annotated_run._logdog_bootstrap, self.rt, self.opts, self.basedir,
        self.tdir, self._config(), self.properties, [])


if __name__ == '__main__':
  unittest.main()
