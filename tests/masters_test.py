#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Starts all mains and verify they can server /json/project fine.
"""

import collections
import contextlib
import glob
import logging
import optparse
import os
import subprocess
import sys
import tempfile
import threading
import time

BUILD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_CONCURRENT_THREADS = 8
sys.path.insert(0, os.path.join(BUILD_DIR, 'scripts'))
import common.env
common.env.Install()

import mains_util
from common import chromium_utils
from common import main_cfg_utils


def do_main_imports():
  # Import scripts/subordinate/bootstrap.py to get access to the ImportMainConfigs
  # function that will pull in every site_config for us. The main config
  # classes are saved as attributes of config_bootstrap.Main. The import
  # takes care of knowing which set of site_configs to use.
  import subordinate.bootstrap
  subordinate.bootstrap.ImportMainConfigs()
  return getattr(sys.modules['config_bootstrap'], 'Main')


@contextlib.contextmanager
def BackupPaths(base_path, path_globs):
  tmpdir = tempfile.mkdtemp(prefix='.tmpMainsTest', dir=base_path)
  paths_to_restore = []
  try:
    for path_glob in path_globs:
      for path in glob.glob(os.path.join(base_path, path_glob)):
        bkup_path = os.path.join(tmpdir, os.path.relpath(path, base_path))
        os.rename(path, bkup_path)
        paths_to_restore.append((path, bkup_path))
    yield
  finally:
    for path, bkup_path in paths_to_restore:
      if subprocess.call(['rm', '-rf', path]) != 0:
        print >> sys.stderr, 'ERROR: failed to remove tmp %s' % path
        continue
      if subprocess.call(['mv', bkup_path, path]) != 0:
        print >> sys.stderr, 'ERROR: mv %s %s' % (bkup_path, path)
    os.rmdir(tmpdir)

def test_main(main, path, name, ports):
  if not mains_util.stop_main(main, path):
    return False
  logging.info('%s Starting', main)
  start = time.time()
  with BackupPaths(path, ['twistd.log', 'twistd.log.?', 'git_poller_*.git',
                          'state.sqlite']):
    try:
      if not mains_util.start_main(main, path, dry_run=True):
        return False
      res = mains_util.wait_for_start(main, name, path, ports)
      if not res:
        logging.info('%s Success in %1.1fs', main, (time.time() - start))
      return res
    finally:
      mains_util.stop_main(main, path, force=True)


class MainTestThread(threading.Thread):
  # Class static. Only access this from the main thread.
  port_lock_map = collections.defaultdict(threading.Lock)

  def __init__(self, main, main_class, main_path):
    super(MainTestThread, self).__init__()
    self.main = main
    self.main_path = main_path
    self.name = main_class.project_name
    all_ports = [
        main_class.main_port, main_class.main_port_alt,
        main_class.subordinate_port, getattr(main_class, 'try_job_port', 0)]
    # Sort port locks numerically to prevent deadlocks.
    self.port_locks = [self.port_lock_map[p] for p in sorted(all_ports) if p]

    # We pass both the read/write and read-only ports, even though querying
    # either one alone would be sufficient sign of success.
    self.ports = [p for p in all_ports[:2] if p]
    self.result = None

  def run(self):
    with contextlib.nested(*self.port_locks):
      self.result = test_main(
          self.main, self.main_path, self.name, self.ports)


def join_threads(started_threads, failed):
  success = 0
  for cur_thread in started_threads:
    cur_thread.join(30)
    if cur_thread.result:
      print '\n=== Error running %s === ' % cur_thread.main
      print cur_thread.result
      failed.add(cur_thread.main)
    else:
      success += 1
  return success


def real_main(all_expected):
  start = time.time()
  main_classes = do_main_imports()
  all_mains = {}
  for base in all_expected:
    base_dir = os.path.join(base, 'mains')
    all_mains[base] = sorted(p for p in
        os.listdir(base_dir) if
        os.path.exists(os.path.join(base_dir, p, 'main.cfg')))
  failed = set()
  skipped = 0
  success = 0

  # First make sure no main is started. Otherwise it could interfere with
  # conflicting port binding.
  if not mains_util.check_for_no_mains():
    return 1
  for base, mains in all_mains.iteritems():
    for main in mains:
      pid_path = os.path.join(base, 'mains', main, 'twistd.pid')
      if os.path.isfile(pid_path):
        pid_value = int(open(pid_path).read().strip())
        if mains_util.pid_exists(pid_value):
          print >> sys.stderr, ('%s is still running as pid %d.' %
              (main, pid_value))
          print >> sys.stderr, 'Please stop it before running the test.'
          return 1


  with main_cfg_utils.TemporaryMainPasswords():
    for base, mains in all_mains.iteritems():
      started_threads = []
      for main in mains[:]:
        if not main in all_expected[base]:
          continue
        mains.remove(main)
        classname = all_expected[base].pop(main)
        if not classname:
          skipped += 1
          continue
        cur_thread = MainTestThread(
            main=main,
            main_class=getattr(main_classes, classname),
            main_path=os.path.join(base, 'mains', main))
        cur_thread.start()
        started_threads.append(cur_thread)
        # Avoid having too many concurrent threads; join if we have reached the
        # limit.
        if len(started_threads) == MAX_CONCURRENT_THREADS:
          success += join_threads(started_threads, failed)
          started_threads = []
      # Join to the remaining started threads.
      if len(started_threads):
        success += join_threads(started_threads, failed)

  if failed:
    print >> sys.stderr, (
        '%d mains failed:\n%s' % (len(failed), '\n'.join(sorted(failed))))
  remaining_mains = []
  for mains in all_mains.itervalues():
    remaining_mains.extend(mains)
  if any(remaining_mains):
    print >> sys.stderr, (
        '%d mains were not expected:\n%s' %
        (len(remaining_mains), '\n'.join(sorted(remaining_mains))))
  outstanding_expected = []
  for expected in all_expected.itervalues():
    outstanding_expected.extend(expected)
  if outstanding_expected:
    print >> sys.stderr, (
        '%d mains were expected but not found:\n%s' %
        (len(outstanding_expected), '\n'.join(sorted(outstanding_expected))))
  print >> sys.stderr, (
      '%s mains succeeded, %d failed, %d skipped in %1.1fs.' % (
        success, len(failed), skipped, time.time() - start))
  return int(bool(remaining_mains or outstanding_expected or failed))


def main(argv):
  parser = optparse.OptionParser()
  parser.add_option('-v', '--verbose', action='count', default=0)
  options, args = parser.parse_args(argv[1:])
  if args:
    parser.error('Unknown args: %s' % args)
  levels = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)
  logging.basicConfig(level=levels[min(options.verbose, len(levels)-1)])

  # Remove site_config's we don't add ourselves. Can cause issues when running
  # this test under a buildbot-spawned process.
  sys.path = [x for x in sys.path if not x.endswith('site_config')]
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  build_internal = os.path.join(os.path.dirname(base_dir), 'build_internal')
  sys.path.extend(os.path.normpath(os.path.join(base_dir, d)) for d in (
      'site_config',
      os.path.join(build_internal, 'site_config'),
  ))
  public_mains = {
      'main.chromium': 'Chromium',
      'main.chromium.android': 'ChromiumAndroid',
      'main.chromium.chrome': 'ChromiumChrome',
      'main.chromium.chromedriver': 'ChromiumChromeDriver',
      'main.chromium.chromiumos': 'ChromiumChromiumos',
      'main.chromium.fyi': 'ChromiumFYI',
      'main.chromium.gatekeeper': 'Gatekeeper',
      'main.chromium.goma': 'ChromiumGoma',
      'main.chromium.gpu': 'ChromiumGPU',
      'main.chromium.gpu.fyi': 'ChromiumGPUFYI',
      'main.chromium.infra': 'Infra',
      'main.chromium.infra.cron': 'InfraCron',
      'main.chromium.linux': 'ChromiumLinux',
      'main.chromium.lkgr': 'ChromiumLKGR',
      'main.chromium.mac': 'ChromiumMac',
      'main.chromium.memory': 'ChromiumMemory',
      'main.chromium.memory.fyi': 'ChromiumMemoryFYI',
      'main.chromium.mojo': 'ChromiumMojo',
      'main.chromium.perf': 'ChromiumPerf',
      'main.chromium.perf.fyi': 'ChromiumPerfFyi',
      'main.chromium.swarm': 'ChromiumSwarm',
      'main.chromium.tools.build': 'ChromiumToolsBuild',
      'main.chromium.webkit': 'ChromiumWebkit',
      'main.chromium.webrtc': 'ChromiumWebRTC',
      'main.chromium.webrtc.fyi': 'ChromiumWebRTCFYI',
      'main.chromium.win': 'ChromiumWin',
      'main.chromiumos': 'ChromiumOS',
      'main.chromiumos.chromium': 'ChromiumOSChromium',
      'main.chromiumos.tryserver': 'ChromiumOSTryServer',
      'main.client.art': 'ART',
      'main.client.boringssl': 'Boringssl',
      'main.client.catapult': 'Catapult',
      'main.client.crashpad': 'ClientCrashpad',
      'main.client.dart': 'Dart',
      'main.client.dart.fyi': 'DartFYI',
      'main.client.dart.packages': 'DartPackages',
      'main.client.drmemory': 'DrMemory',
      'main.client.dynamorio': 'DynamoRIO',
      'main.client.fletch': 'Dartino',
      'main.client.flutter': 'ClientFlutter',
      'main.client.gyp': 'GYP',
      'main.client.legion': 'ClientLegion',
      'main.client.libyuv': 'Libyuv',
      'main.client.libvpx': 'Libvpx',
      'main.client.mojo': 'Mojo',
      'main.client.nacl': 'NativeClient',
      'main.client.nacl.ports': 'WebPorts',
      'main.client.nacl.sdk': 'NativeClientSDK',
      'main.client.nacl.toolchain': 'NativeClientToolchain',
      'main.client.ndk': 'NDK',
      'main.client.pdfium': 'Pdfium',
      'main.client.skia': 'Skia',
      'main.client.skia.android': 'SkiaAndroid',
      'main.client.skia.compile': 'SkiaCompile',
      'main.client.skia.fyi': 'SkiaFYI',
      'main.client.syzygy': 'Syzygy',
      'main.client.v8': 'V8',
      'main.client.v8.branches': 'V8Branches',
      'main.client.v8.fyi': 'V8FYI',
      'main.client.v8.ports': 'V8Ports',
      'main.client.wasm.llvm': 'WasmLlvm',
      'main.client.webrtc': 'WebRTC',
      'main.client.webrtc.fyi': 'WebRTCFYI',
      'main.tryserver.chromium.android': 'TryserverChromiumAndroid',
      'main.tryserver.chromium.angle': 'TryServerANGLE',
      'main.tryserver.chromium.linux': 'TryServerChromiumLinux',
      'main.tryserver.chromium.mac': 'TryServerChromiumMac',
      'main.tryserver.chromium.win': 'TryServerChromiumWin',
      'main.tryserver.chromium.perf': 'ChromiumPerfTryServer',
      'main.tryserver.client.catapult': 'CatapultTryserver',
      'main.tryserver.client.custom_tabs_client': 'CustomTabsClientTryserver',
      'main.tryserver.client.mojo': 'MojoTryServer',
      'main.tryserver.client.pdfium': 'PDFiumTryserver',
      'main.tryserver.client.syzygy': 'SyzygyTryserver',
      'main.tryserver.blink': 'BlinkTryServer',
      'main.tryserver.infra': 'InfraTryServer',
      'main.tryserver.libyuv': 'LibyuvTryServer',
      'main.tryserver.nacl': 'NativeClientTryServer',
      'main.tryserver.v8': 'V8TryServer',
      'main.tryserver.webrtc': 'WebRTCTryServer',
  }
  all_mains = {base_dir: public_mains}
  if os.path.exists(build_internal):
    internal_test_data = chromium_utils.ParsePythonCfg(
        os.path.join(build_internal, 'tests', 'internal_mains_cfg.py'),
        fail_hard=True)
    all_mains[build_internal] = internal_test_data['mains_test']
  return real_main(all_mains)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
