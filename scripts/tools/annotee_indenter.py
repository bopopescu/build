#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""annotee_indenter parses annotated input and indents each step level.

Used by ../subordinate/recipes/infra/try_recipe.py to execute sub-recipes
and indent output automatically.
"""

import argparse
import collections
import errno
import os
import select
import subprocess
import sys
import threading
import Queue


QUEUE_TERMINATE_ITEM = object()


def main(argv):
  parser = argparse.ArgumentParser(os.path.basename(__file__))
  parser.add_argument('--cwd', help='The cwd for executing child process.',
                      default=os.getcwd())
  parser.add_argument('--base-level', help='The base level for indents.',
                      type=int, required=True)
  parser.add_argument('--use-python-executable', action='store_true',
                      help='execute python command using same executbale, '
                           'as running this one.')
  parser.add_argument('sub', nargs='+')
  opts = parser.parse_args(argv)
  cmd = opts.sub
  if opts.use_python_executable:
    cmd = [sys.executable] + cmd
  return run(cmd, opts.cwd, opts.base_level, process_output)


def run(args, cwd, base_level, target):
  proc = subprocess.Popen(args, cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  queue = Queue.Queue()
  t = threading.Thread(target=target, args=(queue, base_level))
  t.start()
  try:
    if sys.platform == "win32":
      communicate_win(proc, queue)
    else:
      communicate_posix(proc, queue)
  finally:
    # Ensure that on KeyboardInterrupt, the thread terminates gracefully.
    queue.put(QUEUE_TERMINATE_ITEM)
    t.join()
  return proc.wait()


def communicate_posix(proc, queue):
  """While process runs, puts tuples of (stream name, data) into queue."""

  def reader(rlist, stream_name):
    stream = getattr(proc, stream_name)
    if stream in rlist:
      data = os.read(stream.fileno(), 1024)
      if data == '':
        stream.close()
        read_set.remove(stream)
      queue.put((stream_name, data))

  read_set = [proc.stdout, proc.stderr]
  while read_set:
    try:
      rlist, _, _ = select.select(read_set, [], [])
    except select.error, e:
      if e.args[0] == errno.EINTR:
        continue
      raise
    reader(rlist, 'stdout')
    reader(rlist, 'stderr')


def communicate_win(proc, queue):
  def reader(stream_name):
    stream = getattr(proc, stream_name)
    while True:
      data = stream.read(1024)
      if data == '':
        break
      queue.put((stream_name, data))

  threads = []
  for stream_name in ['stdout', 'stderr']:
    t = threading.Thread(target=reader, args=(stream_name, ))
    t.daemon = True
    t.start()
    threads.append(t)

  for t in threads:
    t.join()


def line_generator(queue, stderr_stream=None):
  if stderr_stream is None:
    stderr_stream = sys.stderr
  # remainder stores the line which started, but not finished.
  remainder = {}
  while True:
    item = queue.get()
    if item == QUEUE_TERMINATE_ITEM:
      break
    stream, data = item
    data = remainder.pop(stream, '') + data
    if data == '':
      continue
    lines = data.splitlines(True)  # Keep endings.
    if not lines[-1].endswith('\n'):
      # Last line isn't finished yet, put into remainder.
      remainder[stream] = lines.pop()
    for l in lines:
      if stream == 'stderr':
        stderr_stream.write(l)
      else:
        yield l
  # Empty remainder, if any, at the end.
  if 'stderr' in remainder:
    stderr_stream.write(remainder.pop('stderr'))
  if 'stdout' in remainder:
    yield remainder.pop('stdout')
  assert not remainder


def process_output(queue, base_level):
  return indent(base_level, line_generator(queue), sys.stdout)


def indent(base_level, input_lines, output_stream):
  for l in input_lines:
    if l.startswith('@@@STEP_NEST_LEVEL@'):
      # Example: @@@STEP_NEST_LEVEL@1@@@
      level = int(l[len('@@@STEP_NEST_LEVEL@'):].strip().strip('@'))
      l = l.replace(str(level), str(level + base_level))
    output_stream.write(l)
    if l.startswith('@@@STEP_STARTED@@@'):
      output_stream.write('@@@STEP_NEST_LEVEL@%d@@@\n' % base_level)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
