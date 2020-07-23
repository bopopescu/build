#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import bz2
import datetime
import gzip
import inspect
import logging
import logging.handlers
import multiprocessing
import os
import re
import subprocess
import sys
import tempfile
import types
import urlparse

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
# Directory containing build/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
assert os.path.isdir(os.path.join(ROOT_DIR, 'build')), \
                     'Script may have moved in the hierarchy'

sys.path.insert(0, os.path.join(ROOT_DIR, 'build', 'scripts'))
import common.env
common.env.Install()

import requests  # pylint: disable=F0401
import pytz  # pylint: disable=F0401

from common import find_depot_tools
DEPOT_TOOLS_DIR = find_depot_tools.add_depot_tools_to_path()
GSUTIL_BIN = os.path.join(DEPOT_TOOLS_DIR, 'gsutil.py')
assert os.path.isfile(GSUTIL_BIN), 'gsutil may have moved in the hierarchy'

# Define logger as root logger by default. Modified by set_logging() below.
logger = logging


class GSutilError(RuntimeError):
  pass


def call_gsutil(args, dry_run=False, stdin=None):
  """Call gsutil with the specified arguments.

  This function raises OSError when gsutil is not found or not executable.
  No exception is raised when gsutil returns a non-zero code.

  Args:
  args (list or tuple): gsutil arguments
  dry_run (boolean): if True, only prints what would be executed.
  stding (str): string to pass as standard input to gsutil.

  Return:
  (stdout, stderr, returncode) respectively strings containing standard output
     and standard error, and code returned by the process after completion.
  """
  if not isinstance(stdin, (basestring, types.NoneType)):
    raise ValueError('Incorrect type for stdin: must be a string or None.')

  cmd = [GSUTIL_BIN, '--force-version', '4.15', '--']
  cmd.extend(args)
  logger.debug('Running: %s', ' '.join(cmd))
  if dry_run:
    return '', '', 0

  proc = subprocess.Popen(cmd,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
  stdout, stderr = proc.communicate(stdin)
  returncode = proc.returncode

  return stdout, stderr, returncode


class MemStorage(object):
  """An in-memory storage, used for testing."""
  # TODO(pgervais) This class should be dropped while refactoring for better
  # testability.
  def __init__(self, main_name):
    self._main_name = main_name
    self._refs = set()

  def _get_ref(self, builder_name, build_num=None, log_file=''):
    return ('%s/%s/%.7d/%s' % (self._main_name,
                               builder_name,
                               build_num or -1,
                               log_file))

  def get_builds(self, _builder_name):  # pylint: disable=R0201
    return {55, 56}

  def has_build(self, builder_name, build_num):
    ref = self._get_ref(builder_name, build_num)
    return ref in self._refs

  def put(self, builder_name, build_num, log_file, source,
          source_type='filename'):

    allowed_types = ('filename', 'content')
    if not source_type in allowed_types:
      raise ValueError('source_type must be in %s' % str(allowed_types))

    ref = self._get_ref(builder_name, build_num, log_file)
    if source_type == 'filename':
      logger.debug('putting %s as %s', source, ref)
    elif source_type == 'content':
      logger.debug('putting content as %s', ref)
    self._refs.add(ref)

  def mark_upload_started(self, builder_name, build_number):
    ref = self._get_ref(builder_name, build_number)
    logger.debug('Marking upload as started: %s', ref)

  def mark_upload_ended(self, builder_name, build_number):
    ref = self._get_ref(builder_name, build_number)
    logger.debug('Marking upload as done: %s', ref)

  def get_partial_uploads(self, _builder_name):  # pylint: disable=R0201
    return {55}


class GCStorage(object):
  """Google Cloud Storage backend.

  This is specific to buildbot. As such, it understands the notion of
  main, builder, build num and log file name.

  What is called a reference in the following is the tuple
  (main_name, builder_name, build_num, log_file), with main_name being
  implicit, and log_file optional. So (builder_name, build_num) is also a
  reference.
  """
  CHUNK_SIZE = 1000000

  # first path component for flag and log files.
  FLAG_PREFIX = 'flags'
  LOG_PREFIX = 'logs'
  re_number = re.compile('[0-9]+$')

  def __init__(self, main_name, bucket, chunk_size=CHUNK_SIZE, dry_run=False):
    if main_name.startswith('main.'):
      self._main_name = main_name[7:]
    else:
      self._main_name = main_name

    self._bucket = bucket.rstrip('/')
    # chunk to use when uncompressing files.
    self._chunk_size = chunk_size
    self._dry_run = dry_run
    # Cache to know if a build has been uploaded yet
    # self._builders[builder_name] is a set of build numbers (possibly empty.)
    # Beware: build numbers are _str_, not int.
    self._builders = {}

  def _get_ref(self, builder_name, build_num=None, log_file=None,
               prefix=LOG_PREFIX):
    ref = '/'.join((prefix, self._main_name, builder_name))
    if build_num is not None:  # can be zero
      ref += '/%.7d' % build_num
    if log_file is not None:
      if log_file == '':
        raise ValueError('log_file name provided was empty.')

      ref += '/' + log_file
    return ref

  def _get_gs_url(self, builder_name, build_num=None, log_file=None):
    """Compute the gs:// url to get to a log file."""
    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file,
                        prefix=self.LOG_PREFIX)
    return 'gs://' + self._bucket + '/' + ref

  def _get_flag_gs_url(self, builder_name, build_num=None):
    """Compute the gs:// url to get to a build flag file."""
    ref = self._get_ref(builder_name, build_num=build_num,
                        prefix=self.FLAG_PREFIX)
    return 'gs://' + self._bucket + '/' + ref

  def get_http_url(self, builder_name, build_num, log_file=None):
    """Compute the http:// url associated with a ref.

    This function exists mainly for reference purposes.

    See also
    https://developers.google.com/storage/docs/reference-uris
    """
    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file)
    return ('https://storage.cloud.google.com/'
            + self._bucket + '/' + ref.lstrip('/'))

  def get_builds(self, builder_name):
    """Return set of already uploaded builds."""
    build_nums = self._builders.get(builder_name)
    if build_nums is not None:  # could be empty set
      return build_nums

    build_nums = set()
    stdout, stderr, returncode = call_gsutil(['ls',
                                         self._get_gs_url(builder_name)],
                                        dry_run=self._dry_run)
    if returncode != 0:
      # The object can be missing when the builder name hasn't been used yet.
      if not 'matched no objects' in stderr:
        logger.error('Unable to list bucket content.')
        raise GSutilError('Unable to list bucket content. gsutil stderr: %s',
                          stderr)
    else:
      for line in stdout.splitlines():
        num = line.strip('/').split('/')[-1]
        if not self.re_number.match(num):
          raise RuntimeError('Unexpected build number from "gsutil ls": %s'
                             % num)
        build_nums.add(int(num))

    self._builders[builder_name] = build_nums

    return self._builders[builder_name]

  def has_build(self, builder_name, build_num):
    return build_num in self.get_builds(builder_name)

  def _copy_source_to_tempfile(self, source, out_f):
    """Prepare a source file for upload by gsutil.

    source: input file name
    out_f: temporary file. file descriptor (int) of a file open for writing.
    """
    if source.endswith('.bz2'):
      logger.debug('Uncompressing bz2 file...')
      openfunc = lambda: bz2.BZ2File(source, 'rb')
    elif source.endswith('.gz'):
      logger.debug('Uncompressing gz file...')
      openfunc = lambda: gzip.GzipFile(source, 'rb')
    else:
      # TODO(pgervais) could use a symbolic link instead.
      # But beware of race conditions.
      logger.debug('Copying log file')
      openfunc = lambda: open(source, 'rb')

    with openfunc() as in_f:
      while True:
        chunk = in_f.read(self._chunk_size)
        if len(chunk) == 0:
          break
        if not self._dry_run:
          out_f.write(chunk)

  def put(self, builder_name, build_num, log_file, source,
          source_type='filename'):
    """Upload the content of a file to GCS.

    builder_name (str): name of builder as shown on the waterfall
    build_num (int): build number
    log_file (str): name of log file on GCS

    source: path toward the source file to upload or content as string.
    source_type: if 'filename', then the 'source' parameter is a file name.
                 if 'content' then the 'source' parameter is the content itself.

    See also get_http_url()
    """
    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file)
    if source_type == 'filename':
      logger.debug('putting %s as %s', source, ref)
    elif source_type == 'content':
      logger.debug('putting content as %s', ref)

    # The .txt extension is *essential*, so that the mime-type is set to
    # text/plain and not application/octet-stream. There are no options to
    # force the mimetype with the gsutil command (sigh.) 05/07/2014
    with tempfile.NamedTemporaryFile(suffix='_upload_logs_to_storage.txt',
                                     delete=True) as out_f:
      if source_type == 'filename':
        self._copy_source_to_tempfile(source, out_f)
      elif source_type == 'content':
        out_f.write(source)
      else:
        # This is not supposed to be reachable, but leaving it just in case.
        raise ValueError('Invalid value for source_type: %s' % source_type)

      out_f.flush()
      logger.debug('Done uncompressing/copying.')
      _, _, returncode = call_gsutil(
        ['cp', out_f.name, self._get_gs_url(builder_name,
                                            build_num=build_num,
                                            log_file=log_file)],
        dry_run=self._dry_run)

    if returncode == 0:
      logger.info('Successfully uploaded to %s',
                  self.get_http_url(builder_name,
                                    build_num=build_num,
                                    log_file=log_file))
    else:
      logger.info('Failed uploading %s', ref)

  def mark_upload_started(self, builder_name, build_number):
    """Create a flag file on GCS."""
    gs_url = self._get_flag_gs_url(builder_name, build_num=build_number)
    # TODO(pgervais) set IP/hostname, pid, timestamp as flag content

    # Let's be paranoid and prevent bad files from being created.
    num = gs_url.strip('/').split('/')[-1]
    if not self.re_number.match(num):
      logger.error('gs url must end with an integer: %s', gs_url)
      raise ValueError('gs url must end with an integer: %s', gs_url)

    content = 'mark'
    _, stderr, returncode = call_gsutil(['cp', '-', gs_url],
                                        stdin=content,
                                        dry_run=self._dry_run)
    if returncode != 0:
      logger.error('Unable to mark upload as started.')
      logger.error(stderr)
      raise GSutilError('Unable to mark upload as started.')
    else:
      logger.debug('Marked upload as started: %s/%s',
                   builder_name, build_number)

  def mark_upload_ended(self, builder_name, build_number):
    """Remove the flag file on GCS."""
    gs_url = self._get_flag_gs_url(builder_name, build_number)

    # Let's be paranoid. We really don't want to erase a random file.
    assert '*' not in gs_url
    assert gs_url.startswith('gs://')
    file_parts = gs_url[5:].split('/')
    assert file_parts[1] == self.FLAG_PREFIX

    _, _, returncode = call_gsutil(['rm', gs_url], dry_run=self._dry_run)
    if returncode != 0:
      logger.error('Unable to mark upload as done: %s/%s',
                   builder_name, build_number)
      raise GSutilError('Unable to mark upload as done.')
    else:
      logger.debug('Marked upload as done: %s/%s', builder_name, build_number)

  def get_partial_uploads(self, builder_name):
    """Get set of all unfinished uploads."""
    partial_uploads = set()

    stdout, stderr, returncode = call_gsutil(['ls',
                                         self._get_flag_gs_url(builder_name)],
                                        dry_run=self._dry_run)
    if returncode != 0:
      if not 'matched no objects' in stderr:
        logger.error("Unable to list bucket content.")
        raise GSutilError("Unable to list bucket content. gsutil stderr: %s",
                          stderr)
    else:
      for line in stdout.splitlines():
        num = line.strip('/').split('/')[-1]
        if not self.re_number.match(num):
          raise RuntimeError('Unexpected build number from "gsutil ls": %s'
                             % num)
        partial_uploads.add(int(num))

    return partial_uploads


def get_main_directory(main_name):
  """Given a main name, returns the full path to the corresponding directory.

  This function either returns a path to an existing directory, or None.
  """
  if main_name.startswith('main.'):
    main_name = main_name[7:]

  # Look for the main directory
  for build_name in ('build', 'build_internal'):
    main_path = os.path.join(ROOT_DIR,
                               build_name,
                               'mains',
                               'main.' + main_name)

    if os.path.isdir(main_path):
      return main_path
  return None


class Waterfall(object):
  def __init__(self, main_name, url=None):
    logger.debug('Instantiating Waterfall object')

    if main_name.startswith('main.'):
      main_name = main_name[7:]
    self._main_name = main_name
    self._main_path = get_main_directory(self._main_name)

    if not self._main_path:
      logger.error('Cannot find main directory for %s', self._main_name)
      raise ValueError('Cannot find main directory')

    logger.info('Found main directory: %s', self._main_path)

    # Compute URL
    self._url = None
    if url:
      self._url = url.rstrip('/')
      parsed_url = urlparse.urlparse(self._url)
      if parsed_url.scheme not in ('http', 'https'):
        raise ValueError('url should use an http(s) protocol')
    else:  # url not provided, relying on main_site_config.py
      main_site_config_path = os.path.join(self._main_path,
                                             'main_site_config.py')

      if not os.path.isfile(main_site_config_path):
        logger.error('No main_site_config.py file found: %s',
                     main_site_config_path)
        raise OSError('%s not found', main_site_config_path)

      local_vars = {}
      try:
        execfile(main_site_config_path, local_vars)
      # pylint: disable=W0703
      except Exception:
        # Naked exceptions are banned by the style guide but we are
        # trying to be resilient here.
        logger.error('Failure during execution of %s',
                     main_site_config_path)
        raise
      for _, symbol in local_vars.iteritems():
        if inspect.isclass(symbol):
          if not hasattr(symbol, 'main_port'):
            continue
          self._main_port = symbol.main_port
          self._url = 'http://localhost:%d' % self._main_port
          logger.info('Using URL: %s', self._url)
          break

      if not self._url:
        logger.error('No URL could be determined, this can be caused by '
                      'main_site_config.py not having the expected '
                      'structure.')
        raise OSError('No URL could be determined')


  def get_builder_properties(self):
    """Query information about builders

    Return a dict mapping builder name to builder properties, as returned
    by buildbot.
    """
    try:
      return requests.get(self._url + '/json/builders').json()
    except requests.ConnectionError:
      logger.error('Unable to reach %s.', self._url)
      raise

  def get_build_properties(self, builder_name, build_number):
    """Query information about a specific build."""
    r = requests.get(self._url + '/json/builders/%s/builds/%d'
                     % (builder_name, build_number))
    return r.text, r.json()

  def get_log_filenames(self, build_properties, basedir):
    """Compute log file names.

    build_properties (dict): build properties as returned by buildbot.
        Second return value of get_build_properties().
    basedir (string): builder directory containing the log files.
    """
    build_number = build_properties['number']

    step_logs = [(s['name'], loginfo[0])
                 for s in build_properties['steps']
                 for loginfo in s['logs']]
    log_filenames = []

    for step_name, log_name in step_logs:
      # From buildbot, in  status/build.py:generateLogfileName
      basename = '%d-log-%s-%s' % (build_number, step_name, log_name)
      basename = re.sub(r'[^\w\.\-]', '_', basename)
      filename = os.path.join(self._main_path, basedir, basename)
      ref = (build_properties['builderName'],
             build_number,
             re.sub(r'[/\[\]*+?]', '_', step_name) + '.' + log_name)

      for ext in ('', '.gz', '.bz2'):
        filename_ext = filename + ext
        if os.path.isfile(filename_ext):
          log_filenames.append((ref, filename_ext))
          logger.debug('Found log file %s', filename_ext)
          break
      else:
        logger.warning('Skipping non-existing log file %s', filename)
    return log_filenames


def get_options():
  """Configures parser and returns raw options object."""
  parser = argparse.ArgumentParser(description='Upload logs to google storage.',
                                   add_help=False)
  parser.add_argument('--help', action='store_true',
                      help='show help')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='Do not write anything.')
  parser.add_argument('--waterfall-url',
                      help='waterfall main URL. Usually http://localhost:XXXX')
  parser.add_argument('--main-name', required=True,
                      help='name of the main to query. e.g. "chromium"')
  parser.add_argument('--builder-name',
                      help='name of the builder to query. e.g. "Linux"'
                           'Must be under specified main. If unspecified, '
                           'all builders are considered.')
  parser.add_argument('--bucket', default=None,
                      help='name of the bucket to use to upload logs, '
                           'optional.')
  parser.add_argument('--limit', default=10, type=int,
                      help='Maximum number of builds to upload in this run.')
  parser.add_argument('--nice', default=10,
                      help='Amount of niceness to add to this process and its'
                      'subprocesses')
  parser.add_argument('-v', '--verbose', action='count', default=0)

  options = parser.parse_args()
  if options.help:
    parser.print_help()
    sys.exit(0)
  return options


def set_logging(loglevel, output_dir, timezone='US/Pacific'):
  """Sets log level based on how many times -v was specified.

  Defines the logger called 'main'. It prints iso8601 timestamps, that
  include timezone information.
  """
  levels = [
      logging.WARNING,
      logging.INFO,
      logging.DEBUG
  ]

  class Iso8601Filter(logging.Filter):
    def __init__(self, timezone):
      logging.Filter.__init__(self)
      self.tz = pytz.timezone(timezone)

    def filter(self, record):
      dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)
      record.iso8601 = self.tz.normalize(dt).isoformat()
      return True

  formatter = logging.Formatter('%(iso8601)s: %(message)s')

  stdout = logging.StreamHandler()
  stdout.setFormatter(formatter)
  loglevel = min(len(levels) - 1, max(0, loglevel))
  stdout.setLevel(level=levels[loglevel])

  logfile_handler = logging.handlers.RotatingFileHandler(
    os.path.join(output_dir, 'upload_logs_to_storage.log'),
    maxBytes=1048576, backupCount=20)
  logfile_handler.setLevel(level=logging.INFO)
  logfile_handler.setFormatter(formatter)

  global logger
  logger = logging.getLogger('main')
  logger.addFilter(Iso8601Filter(timezone))
  logger.addHandler(stdout)
  logger.addHandler(logfile_handler)
  logger.setLevel(level=logging.DEBUG)


def upload_task(task):
  storage = task['storage']

  # Beginning of critical section
  storage.mark_upload_started(task['builder_name'], task['build_number'])
  storage.put(task['builder_name'], task['build_number'],
              'METADATA', task['build_properties'], source_type='content')

  for ref, log_filename in task['log_filenames']:
    assert ref[0] == task['builder_name']
    assert ref[1] == task['build_number']
    log_name = ref[2]
    storage.put(
        task['builder_name'], task['build_number'], log_name, log_filename)
  storage.mark_upload_ended(task['builder_name'], task['build_number'])
  # End of critical section


def main():
  if not os.path.exists(GSUTIL_BIN):
    print >> sys.stderr, ('gsutil not found in %s\n' % GSUTIL_BIN)
    return 2

  options = get_options()
  set_logging(options.verbose, get_main_directory(options.main_name))
  logger.info('-- uploader starting --')
  os.nice(options.nice)

  w = Waterfall(options.main_name, url=options.waterfall_url)
  builders = w.get_builder_properties()

  if options.bucket:
    storage = GCStorage(options.main_name,
                        options.bucket,
                        dry_run=options.dry_run)
  else:
    storage = MemStorage(options.main_name)

  builder_names = builders.keys()
  if options.builder_name:
    if options.builder_name not in builder_names:
      logger.error("Specified builder (%s) doesn't exist on main",
                   options.builder_name)
      return 1
    builder_names = [options.builder_name]

  upload_tasks = []

  for builder_name in builder_names:
    logger.info('Starting processing builder %s', builder_name)

    # Builds known to buildbot.
    cached_builds = builders[builder_name].get('cachedBuilds', [])
    cached_builds.sort(reverse=True)

    # Builds whose upload is not finished (leftovers from a previous crash.)
    partial_uploads = storage.get_partial_uploads(builder_name)
    if len(partial_uploads) > 100:
      logger.warning('More than 100 partial uploads found.')

    # Build already uploaded
    stored_builds = storage.get_builds(builder_name)

    missing_builds = [
      b for b in cached_builds
      if (b not in stored_builds or b in partial_uploads)
      and b not in builders[builder_name]['currentBuilds']
      ]

    missing_builds_num = len(missing_builds)
    if options.limit:
      missing_builds = missing_builds[:options.limit]
    logger.info('Uploading %d out of %d missing builds',
                len(missing_builds), missing_builds_num)
    logger.info('Builds to upload: %s', str(missing_builds))

    for build_number in missing_builds:
      logger.info('Starting processing build %s/%d',
                  builder_name, build_number)
      build_properties, bp = w.get_build_properties(builder_name, build_number)
      log_filenames = w.get_log_filenames(bp, builders[builder_name]['basedir'])

      upload_tasks.append({
          'storage': storage,
          'builder_name': builder_name,
          'build_number': build_number,
          'build_properties': build_properties,
          'log_filenames': log_filenames,
      })

  pool = multiprocessing.Pool(10)
  pool.map(upload_task, upload_tasks)

  return 0


if __name__ == '__main__':
  try:
    retcode = main()
  except Exception:
    logger.exception("Uncaught exception during execution")
    retcode = 1
  logger.info('-- uploader shutting down with code %d --', retcode)
  sys.exit(retcode)
