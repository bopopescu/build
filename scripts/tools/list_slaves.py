#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A small maintenance tool to list subordinates."""

import json
import optparse
import os
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
    os.pardir)))

from common import chromium_utils


def ProcessShortName(main):
  """Substitutes shortcuts."""
  main = re.sub(r'\bt\b', 'tryserver', main)
  main = re.sub(r'\bc\b', 'chromium', main)
  main = re.sub(r'\bcr\b', 'chrome', main)
  main = re.sub(r'\bco\b', 'chromiumos', main)
  main = re.sub(r'\bcros\b', 'chromeos', main)
  return main


def LoadMain(subordinates, path):
  """Add list of subordinates for a given main to 'subordinates'.

  Args:
    subordinates(list): this list is extended with dicts describing each subordinate from
      the specified main. *This is the output of this function*.
    path(str): path to a main directory
      (e.g. '<leading dirs>/build/mains/main.chromium.infra/')
  """
  cur_subordinates = chromium_utils.GetSubordinatesFromMainPath(path)
  cur_main = os.path.basename(path)
  for cur_subordinate in cur_subordinates:
    cur_subordinate['mainname'] = cur_main
  subordinates.extend(cur_subordinates)


def Main(argv):
  usage = """%prog [options]

Note: t is replaced with 'tryserver', 'c' with chromium' and
      co with 'chromiumos', 'cr' with chrome, 'cros' with 'chromeos'."""

  mains_path = chromium_utils.ListMainsWithSubordinates()

  mains = [os.path.basename(f) for f in mains_path]
  # Strip off 'main.'
  mains = [re.match(r'(main\.|)(.*)', m).group(2) for m in mains]
  parser = optparse.OptionParser(usage=usage)
  group = optparse.OptionGroup(parser, 'Subordinates to process')
  group.add_option('-x', '--main', default=[], action='append',
                   help='Main to use to load the subordinates list.')
  group.add_option('-k', '--kind', action='append', default=[],
                   help='Only subordinates with a substring present in a builder')
  group.add_option('-b', '--builder', action='append', default=[],
                   help='Only subordinates attached to a specific builder')
  group.add_option('--os', action='append', default=[],
                   help='Only subordinates using a specific OS')
  group.add_option('--os-version', action='append', default=[],
                   help='Only subordinates using a specific OS version')
  group.add_option('-s', '--subordinate', action='append', default=[])
  group.add_option('--cq',
                   help='Only subordinates used by specific CQ (commit queue) config')
  parser.add_option_group(group)
  group = optparse.OptionGroup(parser, 'Output format')
  group.add_option('-n', '--name', default='host',
                   dest='fmt', action='store_const', const='host',
                   help='Output subordinate hostname')
  group.add_option('-r', '--raw',
                   dest='fmt', action='store_const', const='raw',
                   help='Output all subordinate info')
  group.add_option('-t', '--assignment',
                   dest='fmt', action='store_const', const='assignment',
                   help='Output subordinate tasks too')
  group.add_option('', '--botmap',
                   dest='fmt', action='store_const', const='botmap',
                   help='Output botmap style')
  group.add_option('-w', '--waterfall',
                   dest='fmt', action='store_const', const='waterfall',
                   help='Output subordinate main and tasks')
  group.add_option('', '--json',
                   dest='fmt', action='store_const', const='json',
                   help='Output subordinate list as JSON')
  parser.add_option_group(group)
  options, args = parser.parse_args(argv)
  if args:
    parser.error('Unknown argument(s): %s\n' % args)

  subordinates = []

  if not options.main:
    # Populates by default with every main with a twistd.pid, thus has
    # been started.
    for m_p in mains_path:
      if os.path.isfile(os.path.join(m_p, 'twistd.pid')):
        LoadMain(subordinates, m_p)
  else:
    for main in options.main:
      if main == 'allcros':
        for m in (m for m in mains if (m.startswith('chromeos') or
                                         m.startswith('chromiumos'))):
          LoadMain(subordinates, mains_path[mains.index(m)])
      elif main == 'all':
        for m_p in mains_path:
          LoadMain(subordinates, m_p)
        subordinates.sort(key=lambda x: (x['mainname'], x.get('hostname')))
      else:
        if not main in mains:
          main = ProcessShortName(main)
        if not main in mains:
          parser.error('Unknown main \'%s\'.\nChoices are: %s' % (
            main, ', '.join(mains)))
        LoadMain(subordinates, mains_path[mains.index(main)])

  if options.kind:
    def kind_interested_in_any(builders):
      if isinstance(builders, basestring):
        return any(builders.find(k) >= 0 for k in options.kind)
      return any(any(x.find(k) >= 0 for k in options.kind) for x in builders)
    subordinates = [s for s in subordinates if kind_interested_in_any(s.get('builder'))]

  if options.builder:
    builders = set(options.builder)
    def builder_interested_in_any(x):
      return builders.intersection(set(x))
    subordinates = [s for s in subordinates
              if builder_interested_in_any(s.get('builder', []))]

  if options.os:
    selected = set(options.os)
    subordinates = [s for s in subordinates if s.get('os', 'unknown') in selected]

  if options.os_version:
    selected = set(options.os_version)
    subordinates = [s for s in subordinates if s.get('version', 'unknown') in selected]

  if options.subordinate:
    selected = set(options.subordinate)
    subordinates = [s for s in subordinates if s.get('hostname') in selected]

  if options.cq:
    with open(options.cq) as f:
      cq_config = json.load(f)

    # Handle CQ configs still remaining in the CQ repo (as opposed to project
    # repos, see http://crbug.com/443613 .
    legacy_config = cq_config.get(
        'verifiers_no_patch', {}).get('try_job_verifier')
    if not legacy_config:
      legacy_config = cq_config.get(
          'verifiers', {}).get('try_job_verifier')
    if legacy_config:
      cq_config = {'trybots': legacy_config}

    def is_used_by_cq(subordinate):
      def get_cq_builders(key):
        return cq_config.get('trybots', {}).get(key, {}).get(
            subordinate['mainname'].replace('main.', ''), {}).keys()
      cq_builders = set(
          get_cq_builders('launched') + get_cq_builders('triggered'))
      return bool(cq_builders.intersection(set(subordinate.get('builder', []))))
    subordinates = [s for s in subordinates if is_used_by_cq(s)]

  if options.fmt == 'json':
    normalized = []
    for s in subordinates:
      host = s.get('hostname')
      if host:
        builder = s.get('builder') or []
        if isinstance(builder, basestring):
          builder = [builder]
        assert isinstance(builder, list)
        s['builder'] = sorted(builder)
        normalized.append(s)
    json.dump(
        sorted(normalized, key=lambda s: (s.get('mainname'), s['hostname'])),
        sys.stdout, sort_keys=True, indent=2, separators=(',', ': '))
    sys.stdout.write('\n')
    return

  for s in subordinates:
    if options.fmt == 'raw':
      print s
    elif options.fmt == 'assignment':
      print s.get('hostname', 'unknown'), ':', s.get('builder', 'unknown')
    elif options.fmt == 'waterfall':
      print s.get('hostname', 'unknown'), ':', s.get('main', 'unknown'), \
            ':', s.get('builder', 'unknown')
    elif options.fmt == 'main':
      print s.get('hostname', 'unknown'), ':', s.get('mainname', 'unknown'), \
            ':', s.get('builder', 'unknown')
    elif options.fmt == 'botmap':
      host = s.get('hostname')
      if host:
        main = s.get('mainname') or '?'
        subordinateos = s.get('os') or '?'
        pathsep = '\\' if s.get('os') == 'win' else '/'
        if 'subdir' in s:
          d = (pathsep + 'b' + pathsep + 'build' + pathsep + 'nested' +
               pathsep + s['subdir'])
        else:
          d = pathsep + 'b'
        builders = s.get('builder') or '?'
        if type(builders) is not list:
          builders = [builders]
        for b in sorted(builders):
          print '%-30s %-20s %-35s %-35s %-10s' % (host, d, main, b, subordinateos)
    else:
      print s.get('hostname', 'unknown')


if __name__ == '__main__':
  sys.exit(Main(None))
