#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import shutil
import sys
import time


# Unless otherwise noted, all ages are in seconds and all sizes are in bytes.


def DAYS(secs):
  return float(secs) / (60 * 60 * 24)


def gen_mains_dirs(build_dir):
  msdir = os.path.join(build_dir, 'mains')
  return [os.path.join(msdir, x) for x in os.listdir(msdir)
          if x.startswith('main') and os.path.isdir(os.path.join(msdir, x))]


def is_builder_dir(bdir):
  if not os.path.isdir(bdir):
    return False
  # It seems buildbot puts this file into every builder directory.
  if not os.path.exists(os.path.join(bdir, 'builder')):
    return False
  if not os.path.isfile(os.path.join(bdir, 'builder')):
    return False
  return True


def get_change_time(f):
  return os.stat(f).st_mtime


def get_age(f):
  return time.time() - get_change_time(f)


def get_size(f):
  return os.stat(f).st_size


def get_builders(mdir):
  for d in os.listdir(mdir):
    bdir = os.path.join(mdir, d)
    if is_builder_dir(bdir):
      yield bdir


def find_builders(build_dir):
  for mdir in gen_mains_dirs(build_dir):
    for bdir in get_builders(mdir):
      yield bdir


def get_dir_size(d):
  s = 0
  for p in os.listdir(d):
    f = os.path.join(d, p)
    if os.path.isdir(f):
      s += get_dir_size(f)
    else:
      s += get_size(f)
  return s


def MiB(size):
  return float(size) / (1024**2)


def preformat_build_dir(bdir, size=None, age=None):
  builder = os.path.basename(bdir)
  main = os.path.basename(os.path.dirname(bdir))
  if size is None:
    size = get_dir_size(bdir)
  if age is None:
    age = get_age(bdir)
  return (main, builder, '%.0f days' % DAYS(age), '%.1f MiB' % MiB(size))


def preformat_build_logs(bdir, logs, size):
  builder = os.path.basename(bdir)
  main = os.path.basename(os.path.dirname(bdir))
  build_min, build_max = min(logs), max(logs)
  builds_range = 'builds ~ %6i(%4.f days) .. %6i(%4.0f days)' % (
      build_min, DAYS(get_logs_age(logs[build_min])),
      build_max, DAYS(get_logs_age(logs[build_max])))
  return (main, builder, builds_range, '%.1f MiB' % MiB(size))


def print_table(table):
  max_lens = [0] * len(table[0])
  for row in table:
    for i, cell in enumerate(row):
      max_lens[i] = max(len(cell), max_lens[i])
  fmt = '\t'.join('%' + str(l) + 's' for l in max_lens)
  for row in table:
    print fmt % row


def get_logs_age(logs):
  """Returns age of the most recent logfile."""
  return min(map(get_age, logs))


def get_old_logs(bdir, min_age_days):
  """Return tuple ({build_number: logfiles}, number of logs, total size)."""
  # Delete either all files from a build OR none.
  # Hence, first scan to get all log files.
  build_logs = {}
  for f in os.listdir(bdir):
    if f == 'builder':  # Skip this special file.
      continue
    try:
      build_number = int(f.split('-')[0])
    except (ValueError, TypeError, IndexError):
      continue
    logfile = os.path.join(bdir, f)
    build_logs.setdefault(build_number, []).append(logfile)
  # Second scan by buildnumber, modifying logs dict inside loop.
  count, size = 0, 0
  for build_number, logfiles in list(build_logs.iteritems()):
    if DAYS(get_logs_age(logfiles)) < min_age_days:
      build_logs.pop(build_number)
      continue
    count += len(logfiles)
    size += sum(map(get_size, logfiles))
  return build_logs, count, size


def delete_old_logs(opts):
  index = {}  # sort_key => build_number => list of logs files.
  total_size, total_count = 0, 0
  for bdir in find_builders(opts.build_dir):
    age = get_age(bdir)
    if DAYS(age) > opts.min_age_days:
      print ('WARNING: builder is %.0f DAYS old, '
             'consider deleting it completely instead.' % DAYS(age))
      if not opts.force:
        raise Exception('maybe first do: $ %s --min-age-days %i ?' % (
                         os.path.basename(__file__), opts.min_age_days))
    build_logs, count, size = get_old_logs(bdir, opts.min_age_days)
    if not build_logs:
      assert count == 0 and size == 0
      continue
    index[(size, count, bdir)] = build_logs
    total_size += size
    total_count += count

  table = []
  for k in sorted(index, reverse=True):
    size, _, bdir = k
    table.append(preformat_build_logs(bdir, index[k], size))
  print_table(table)

  metrics = '%i logfiles weighing %0.f MiB' % (total_count, MiB(total_size))
  if opts.force:
    print 'deleting these logs files (%s)' % metrics
  else:
    prompt = 'do you want to delete these logs (%s)?' % metrics
    if raw_input(prompt).strip().lower() not in ('y', 'yes'):
      print 'aborting.'
      return 0

  for size, count, bdir in sorted(index, reverse=True):
    print 'cleaning %5i logfiles weighing %5.0f MiB in %s...' % (
          count, MiB(size), bdir)
    if opts.dry_run:
      continue
    for logfiles in index[(size, count, bdir)].itervalues():
      for logfile in logfiles:
        assert DAYS(get_age(logfile)) > opts.min_age_days
        os.remove(logfile)
  print 'done%s.' % (' (dry run)' if opts.dry_run else '')


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument(
      'build_dir',
      help='path to either build/ or build_internal/')
  parser.add_argument(
      '--just-logs', default=False, action='store_true',
      help=('delete individual build log files instead of builder directories. '
            'WARNING: this will change the mod time of a builder dir, thus '
            'making it younger to this script than it actually was. It\'s '
            'recommended that you *first* prune old builddirs completely, '
            'and then delete individual logs.'))
  parser.add_argument(
      '--min-age-days', type=int,
      help='min age in days to be considered for deletion')
  parser.add_argument(
      '--min-size-mib', type=int,
      help='min size in MiB to be considered for deletion')
  parser.add_argument(
      '-d', '--dry-run', action='store_true', default=False,
      help='do not actually delete dirs')
  parser.add_argument(
      '-f', '--force', action='store_true', default=False,
      help=('do not ask for confirmation. '
           'This isn\'t allowed if min age is less than 1 month.'))
  opts = parser.parse_args(args)
  if opts.force and opts.min_age_days < 30:
    parser.error('safety feature: '
                 '--force can\'t be used to delete too recent log files.')
  if opts.just_logs:
    if opts.min_size_mib:
      parser.error('--min-size-mib can\'t be used with --just-logs')
    return delete_old_logs(opts)
  else:
    return delete_old_builders(opts)


def delete_old_builders(opts):
  # TODO(tandrii): move above main after review
  index = {}
  total_size = 0
  for bdir in find_builders(opts.build_dir):
    age = get_age(bdir)
    if DAYS(age) < opts.min_age_days:
      continue
    size = get_dir_size(bdir)
    if MiB(size) < opts.min_size_mib:
      continue
    total_size += size
    index[(-size, -age, bdir)] = preformat_build_dir(bdir, size, age)
  print_table([index[k] for k in sorted(index)])

  total_size_str = 'total size: %0.f MiB' % MiB(total_size)
  if opts.force:
    print 'deleting these builders dirs (%s)' % total_size_str
  else:
    prompt = 'do you want to delete these builder dirs (%s)?' % total_size_str
    if raw_input(prompt).strip().lower() not in ('y', 'yes'):
      print 'aborting.'
      return 0

  for key in index:
    bdir = key[-1]
    print 'removing %s...' % bdir
    if not opts.dry_run:
      shutil.rmtree(bdir)
  print 'done%s.' % (' (dry run)' if opts.dry_run else '')


if __name__ == '__main__':
  main(sys.argv[1:])
