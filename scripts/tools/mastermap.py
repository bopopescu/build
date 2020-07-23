#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

r"""Tool for viewing mains, their hosts and their ports.

Has three modes:
  a) In normal mode, simply prints the list of all known mains, sorted by
     hostname, along with their associated ports, for the perusal of the user.
  b) In --audit mode, tests to make sure that no mains conflict/overlap on
     ports (even on different mains) and that no mains have unexpected
     ports (i.e. differences of more than 100 between main, subordinate, and alt).
     Audit mode returns non-zero error code if conflicts are found. In audit
     mode, --verbose causes it to print human-readable output as well.
  c) In --find mode, prints a set of available ports for the given main
     class.

Ports are well-formed if they follow this spec:
XYYZZ
|| \__The last two digits identify the main, e.g. main.chromium
|\____The second and third digits identify the main host, e.g. main1.golo
\_____The first digit identifies the port type, e.g. main_port

In particular,
X==3: main_port (Web display)
X==4: subordinate_port (for subordinate TCP/RCP connections)
X==5: main_port_alt (Alt web display, with "force build" disabled)
The values X==1,2, and 6 are not used due to too few free ports in those ranges.

In all modes, --csv causes the output (if any) to be formatted as
comma-separated values.
"""

import argparse
import json
import os
import sys

# Should be <snip>/build/scripts/tools
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir, os.pardir))
sys.path.insert(0, os.path.join(BASE_DIR, 'scripts'))
sys.path.insert(0, os.path.join(BASE_DIR, 'site_config'))

import config_bootstrap
from config_bootstrap import Main
from subordinate import bootstrap


# These are ports which are likely to be used by another service, or which have
# been officially reserved by IANA.
PORT_BLACKLIST = set([
    # We don't care about reserved ports below 30000, the lowest port we use.
    31457,  # TetriNET
    31620,  # LM-MON
    33434,  # traceroute
    34567,  # EDI service
    35357,  # OpenStack ID Service
    40000,  # SafetyNET p Real-time Industrial Ethernet protocol
    41794,  # Crestron Control Port
    41795,  # Crestron Control Port
    45824,  # Server for the DAI family of client-server products
    47001,  # WinRM
    47808,  # BACnet Building Automation and Control Networks
    48653,  # Robot Raconteur transport
    49151,  # Reserved
    # There are no reserved ports in the 50000-65535 range.
])


PORT_RANGE_MAP = {
  'port': Main.Base.MASTER_PORT_RANGE,
  'subordinate_port': Main.Base.SLAVE_PORT_RANGE,
  'alt_port': Main.Base.MASTER_PORT_ALT_RANGE,
}


# A map of (full) main host to main class used in 'get_main_class'
# lookup.
MASTER_HOST_MAP = dict((m.main_host, m)
                       for m in Main.get_base_mains())


def get_args():
  """Process command-line arguments."""
  parser = argparse.ArgumentParser(
      description='Tool to list all mains along with their hosts and ports.')

  parser.add_argument(
      '-l', '--list', action='store_true', default=False,
      help='Output a list of all ports in use by all mains. Default behavior'
           ' if no other options are given.')
  parser.add_argument(
      '--sort-by', action='store',
      help='Define the primary key by which rows are sorted. Possible values '
           'are: "port", "alt_port", "subordinate_port", "host", and "name". Only '
           'one value is allowed (for now).')
  parser.add_argument(
      '--find', action='store', metavar='NAME',
      help='Outputs three available ports for the given main class.')
  parser.add_argument(
      '--audit', action='store_true', default=False,
      help='Output conflict diagnostics and return an error code if '
           'misconfigurations are found.')
  parser.add_argument(
      '--presubmit', action='store_true', default=False,
      help='The same as --audit, but prints no output. Overrides all other '
           'options.')

  parser.add_argument(
      '-f', '--format', choices=['human', 'csv', 'json'],
      default='human', help='Print output in the given format')
  parser.add_argument(
      '--full-host-names', action='store_true', default=False,
      help='Refrain from truncating the main host names')

  opts = parser.parse_args()

  opts.verbose = True

  if not (opts.find or opts.audit or opts.presubmit):
    opts.list = True

  if opts.presubmit:
    opts.list = False
    opts.audit = True
    opts.find = False
    opts.verbose = False

  return opts


def getint(string):
  """Try to parse an int (port number) from a string."""
  try:
    ret = int(string)
  except ValueError:
    ret = 0
  return ret


def print_columns_human(lines, verbose):
  """Given a list of lists of tokens, pretty prints them in columns.

  Requires all lines to have the same number of tokens, as otherwise the desired
  behavior is not clearly defined (i.e. which columns should be left empty for
  shorter lines?).
  """

  for line in lines:
    assert len(line) == len(lines[0])

  num_cols = len(lines[0])
  format_string = ''
  for col in xrange(num_cols - 1):
    col_width = max(len(str(line[col])) for line in lines) + 1
    format_string += '%-' + str(col_width) + 's '
  format_string += '%s'

  if verbose:
    for line in lines:
      print format_string % tuple(line)


def print_columns_csv(lines, verbose):
  """Given a list of lists of tokens, prints them as comma-separated values.

  Requires all lines to have the same number of tokens, as otherwise the desired
  behavior is not clearly defined (i.e. which columns should be left empty for
  shorter lines?).
  """

  for line in lines:
    assert len(line) == len(lines[0])

  if verbose:
    for line in lines:
      print ','.join(str(t) for t in line)
    print '\n'


def extract_columns(spec, data):
  """Transforms some data into a format suitable for print_columns_...

  The data is a list of anything, to which the spec functions will be applied.

  The spec is a list of tuples representing the column names
  and how to the column from a row of data.  E.g.

  [ ('Main', lambda m: m['name']),
    ('Config Dir', lambda m: m['dirname']),
    ...
  ]
  """

  lines = [ [ s[0] for s in spec ] ]  # Column titles.

  for item in data:
    lines.append([ s[1](item) for s in spec ])
  return lines



def field(name):
  """Returns a function that extracts a particular field of a dictionary."""
  return lambda d: d[name]


def main_map(mains, output, opts):
  """Display a list of mains and their associated hosts and ports."""

  host_key = 'host' if not opts.full_host_names else 'fullhost'

  output([ ('Main', field('name')),
           ('Config Dir', field('dirname')),
           ('Host', field(host_key)),
           ('Web port', field('port')),
           ('Subordinate port', field('subordinate_port')),
           ('Alt port', field('alt_port')),
           ('URL', field('buildbot_url')) ],
         mains)


def get_main_class(main):
  return MASTER_HOST_MAP.get(main['fullhost'])


def get_main_port(main):
  main_class = get_main_class(main)
  if not main_class:
    return None
  return '%02d' % (main_class.main_port_base,)


def main_audit(mains, output, opts):
  """Check for port conflicts and misconfigurations on mains.

  Outputs lists of mains whose ports conflict and who have misconfigured
  ports. If any misconfigurations are found, returns a non-zero error code.
  """

  # Return value. Will be set to 1 the first time we see an error.
  ret = 0

  # Look for mains using the wrong ports for their port types.
  bad_port_mains = []
  for main in mains:
    for port_type, port_range in PORT_RANGE_MAP.iteritems():
      if not port_range.contains(main[port_type]):
        ret = 1
        bad_port_mains.append(main)
        break
  output([ ('Mains with misconfigured ports based on port type',
            field('name')) ],
         bad_port_mains)

  # Look for mains using the wrong ports for their hostname.
  bad_host_mains = []
  for main in mains:
    digits = get_main_port(main)
    if digits:
      for port_type, port_range in PORT_RANGE_MAP.iteritems():
        if ('%04d' % port_range.offset_of(main[port_type]))[0:2] != digits:
          ret = 1
          bad_host_mains.append(main)
          break
  output([ ('Mains with misconfigured ports based on hostname',
            field('name')) ],
         bad_host_mains)

  # Look for mains configured to use the same ports.
  web_ports = {}
  subordinate_ports = {}
  alt_ports = {}
  all_ports = {}
  for main in mains:
    web_ports.setdefault(main['port'], []).append(main)
    subordinate_ports.setdefault(main['subordinate_port'], []).append(main)
    alt_ports.setdefault(main['alt_port'], []).append(main)

    for port_type in ('port', 'subordinate_port', 'alt_port'):
      all_ports.setdefault(main[port_type], []).append(main)

  # Check for blacklisted ports.
  blacklisted_ports = []
  for port, lst in all_ports.iteritems():
    if port in PORT_BLACKLIST:
      ret = 1
      for m in lst:
        blacklisted_ports.append(
            { 'port': port, 'name': m['name'], 'host': m['host'] })
  output([ ('Blacklisted port', field('port')),
           ('Main', field('name')),
           ('Host', field('host')) ],
         blacklisted_ports)

  # Check for conflicting web ports.
  conflicting_web_ports = []
  for port, lst in web_ports.iteritems():
    if len(lst) > 1:
      ret = 1
      for m in lst:
        conflicting_web_ports.append(
            { 'web_port': port, 'name': m['name'], 'host': m['host'] })
  output([ ('Web port', field('web_port')),
           ('Main', field('name')),
           ('Host', field('host')) ],
         conflicting_web_ports)

  # Check for conflicting subordinate ports.
  conflicting_subordinate_ports = []
  for port, lst in subordinate_ports.iteritems():
    if len(lst) > 1:
      ret = 1
      for m in lst:
        conflicting_subordinate_ports.append(
            { 'subordinate_port': port, 'name': m['name'], 'host': m['host'] })
  output([ ('Subordinate port', field('subordinate_port') ),
           ('Main', field('name')),
           ('Host', field('host')) ],
         conflicting_subordinate_ports)

  # Check for conflicting alt ports.
  conflicting_alt_ports = []
  for port, lst in alt_ports.iteritems():
    if len(lst) > 1:
      ret = 1
      for m in lst:
        conflicting_alt_ports.append(
            { 'alt_port': port, 'name': m['name'], 'host': m['host'] })
  output([ ('Alt port', field('alt_port')),
           ('Main', field('name')),
           ('Host', field('host')) ],
         conflicting_alt_ports)

  # Look for mains whose port, subordinate_port, alt_port aren't separated by 5000.
  bad_sep_mains = []
  for main in mains:
    if (getint(main['subordinate_port']) - getint(main['alt_port']) != 5000 or
        getint(main['alt_port']) - getint(main['port']) != 5000):
      ret = 1
      bad_sep_mains.append(main)
  output([ ('Main', field('name')),
           ('Host', field('host')),
           ('Web port', field('port')),
           ('Subordinate port', field('subordinate_port')),
           ('Alt port', field('alt_port')) ],
         bad_sep_mains)

  return ret


def build_port_str(main_class, port_type, digits):
  port_range = PORT_RANGE_MAP[port_type]
  port = str(port_range.compose_port(
      main_class.main_port_base * 100 + digits))
  assert len(port) == 5, "Invalid port generated (%s)" % (port,)
  return port


def find_port(main_class_name, mains, output, opts):
  """Finds a triplet of free ports appropriate for the given main."""
  try:
    main_class = getattr(Main, main_class_name)
  except AttributeError:
    raise ValueError('Main class %s does not exist' % main_class_name)

  used_ports = set()
  for m in mains:
    for port in ('port', 'subordinate_port', 'alt_port'):
      used_ports.add(m.get(port, 0))
  used_ports = used_ports | PORT_BLACKLIST

  def _inner_loop():
    for digits in xrange(0, 100):
      port = build_port_str(main_class, 'port', digits)
      subordinate_port = build_port_str(main_class, 'subordinate_port', digits)
      alt_port = build_port_str(main_class, 'alt_port', digits)
      if all([
          int(port) not in used_ports,
          int(subordinate_port) not in used_ports,
          int(alt_port) not in used_ports]):
        return port, subordinate_port, alt_port
    return None, None, None
  port, subordinate_port, alt_port = _inner_loop()

  if not all([port, subordinate_port, alt_port]):
    raise RuntimeError('Unable to find available ports on host')

  output([ ('Main', field('main_base_class')),
           ('Port', field('main_port')),
           ('Alt port', field('main_port_alt')),
           ('Subordinate port', field('subordinate_port')) ],
         [ { 'main_base_class': main_class_name,
           'main_port': port,
           'main_port_alt': alt_port,
           'subordinate_port': subordinate_port } ])


def format_host_name(host):
  for suffix in ('.chromium.org', '.corp.google.com'):
    if host.endswith(suffix):
      return host[:-len(suffix)]
  return host


def extract_mains():
  """Extracts the data we want from a collection of possibly-mains."""
  good_mains = []
  for main in config_bootstrap.Main.get_all_mains():
    host = getattr(main, 'main_host', '')
    local_config_path = getattr(main, 'local_config_path', '')
    build_dir = os.path.basename(os.path.abspath(os.path.join(local_config_path,
                                                        os.pardir, os.pardir)))
    is_internal = build_dir == 'build_internal'
    good_mains.append({
        'name': main.__name__,
        'host': format_host_name(host),
        'fullhost': host,
        'port': getattr(main, 'main_port', 0),
        'subordinate_port': getattr(main, 'subordinate_port', 0),
        'alt_port': getattr(main, 'main_port_alt', 0),
        'buildbot_url': getattr(main, 'buildbot_url', ''),
        'dirname': os.path.basename(local_config_path),
        'internal': is_internal
    })
  return good_mains


def real_main(include_internal=False):
  opts = get_args()

  bootstrap.ImportMainConfigs(include_internal=include_internal)

  mains = extract_mains()

  # Define sorting order
  sort_keys = ['host', 'port', 'alt_port', 'subordinate_port', 'name']
  # Move key specified on command-line to the front of the list
  if opts.sort_by is not None:
    try:
      index = sort_keys.index(opts.sort_by)
    except ValueError:
      pass
    else:
      sort_keys.insert(0, sort_keys.pop(index))

  for key in reversed(sort_keys):
    mains.sort(key=lambda m: m[key])  # pylint: disable=cell-var-from-loop

  def output_csv(spec, data):
    print_columns_csv(extract_columns(spec, data), opts.verbose)
    print

  def output_human(spec, data):
    print_columns_human(extract_columns(spec, data), opts.verbose)
    print

  def output_json(spec, data):
    print json.dumps(data, sort_keys=True, indent=2, separators=(',', ': '))

  output = {
      'csv': output_csv,
      'human': output_human,
      'json': output_json,
    }[opts.format]

  if opts.list:
    main_map(mains, output, opts)

  ret = 0
  if opts.audit or opts.presubmit:
    ret = main_audit(mains, output, opts)

  if opts.find:
    find_port(opts.find, mains, output, opts)

  return ret


def main():
  return real_main(include_internal=False)


if __name__ == '__main__':
  sys.exit(main())
