#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from common import chromium_utils


START_WITH_LETTER, NUMBER_ONLY = range(2)


def EntryToHostName(entry):
  """Extracts the buildbot host name from the subordinates list entry.

  The subordinate list entry is a dict."""
  return entry.get('hostname', None)


def _obj_as_list(obj):
  """Converts strings as 1 entry list."""
  if not isinstance(obj, (tuple, list)):
    return [obj]
  return obj


def _lower_values(s):
  """Returns a list of strings lower()'ed.

  If a string is passed, a one item list is returned.
  """
  return [x.lower() for x in _obj_as_list(s)]


def _Filter(subordinates, key, value, acceptable):
  """Filters subordinates to keep only those with value in key,
  subordinates[key] being a list or converted to a list.

  Prefix value with - to filter negatively.
  """
  if not value:
    return subordinates
  if isinstance(value, int):
    value = str(value)
  value = value.lower()
  negative = value.startswith('-')
  if negative:
    value = value[1:]
  if acceptable is START_WITH_LETTER:
    assert value[0].isalpha(), value
  elif acceptable is NUMBER_ONLY:
    assert value.isdigit(), value
  else:
    assert acceptable is None
  if negative:
    return [s for s in subordinates if value not in _lower_values(s.get(key, []))]
  else:
    return [s for s in subordinates if value in _lower_values(s.get(key, []))]


def _CheckDupes(items):
  dupes = set()
  while items:
    x = items.pop()
    assert x
    if x in items:
      dupes.add(x)
  if dupes:
    print >> sys.stderr, 'Found subordinate dupes!\n  %s' % ', '.join(dupes)
    assert False, ', '.join(dupes)


class BaseSubordinatesList(object):
  def __init__(self, subordinates, default_main=None):
    self.subordinates = subordinates
    self.default_main = default_main
    _CheckDupes(
        [chromium_utils.EntryToSubordinateName(x).lower() for x in self.subordinates])

  def GetSubordinates(self, main=None, builder=None, os=None, tester=None,
                bits=None, version=None):
    """Returns the subordinates listed in the private/subordinates_list.py file.

    Optionally filter with main, builder, os, tester and bitness type.
    """
    subordinates = self.subordinates
    subordinates = _Filter(
        subordinates, 'main', main or self.default_main, START_WITH_LETTER)
    subordinates = _Filter(subordinates, 'os', os, START_WITH_LETTER)
    subordinates = _Filter(subordinates, 'bits', bits, NUMBER_ONLY)
    subordinates = _Filter(subordinates, 'version', version, None)
    subordinates = _Filter(subordinates, 'builder', builder, START_WITH_LETTER)
    subordinates = _Filter(subordinates, 'tester', tester, START_WITH_LETTER)
    return subordinates

  def GetSubordinate(self, main=None, builder=None, os=None, tester=None, bits=None,
               version=None):
    """Returns one subordinate or none if none or multiple subordinates are found."""
    subordinates = self.GetSubordinates(main, builder, os, tester, bits, version)
    if len(subordinates) != 1:
      return None
    return subordinates[0]

  def GetSubordinatesName(self, main=None, builder=None, os=None, tester=None,
                    bits=None, version=None):
    """Similar to GetSubordinates() except that it only returns the subordinate names."""
    return [
        chromium_utils.EntryToSubordinateName(e)
        for e in self.GetSubordinates(main, builder, os, tester, bits, version)
    ]

  def GetSubordinateName(self, main=None, builder=None, os=None, tester=None,
                   bits=None, version=None):
    """Similar to GetSubordinate() except that it only returns the subordinate name."""
    return chromium_utils.EntryToSubordinateName(
        self.GetSubordinate(main, builder, os, tester, bits, version))

  def GetHostName(self, main=None, builder=None, os=None, tester=None,
                   bits=None, version=None):
    """Similar to GetSubordinate() except that it only returns the host name."""
    return EntryToHostName(
        self.GetSubordinate(main, builder, os, tester, bits, version))

  def GetPreferredBuildersDict(self, main=None, builder=None, os=None,
                               tester=None, bits=None, version=None):
    """Make a dict that is from subordinate name to preferred_builder."""
    d = {}
    for e in self.GetSubordinates(main, builder, os, tester, bits, version):
      if e.has_key('preferred_builder'):
        d[chromium_utils.EntryToSubordinateName(e)] = e.get('preferred_builder')
    return d


class SubordinatesList(BaseSubordinatesList):
  def __init__(self, filename, default_main=None):
    super(SubordinatesList, self).__init__(
        chromium_utils.RunSubordinatesCfg(filename), default_main)


def Main(argv=None):
  import optparse
  parser = optparse.OptionParser()
  parser.add_option('-f', '--filename', help='File to parse, REQUIRED')
  parser.add_option('-m', '--main', help='Main to filter')
  parser.add_option('-b', '--builder', help='Builder to filter')
  parser.add_option('-o', '--os', help='OS to filter')
  parser.add_option('-t', '--tester', help='Tester to filter')
  parser.add_option('-v', '--version', help='OS\'s version to filter')
  parser.add_option('--bits', help='OS bitness to filter', type='int')
  options, _ = parser.parse_args(argv)
  if not options.filename:
    parser.print_help()
    print '\nYou must specify a file to get the subordinate list from'
    return 1
  subordinates = SubordinatesList(options.filename)
  for subordinate in subordinates.GetSubordinatesName(options.main, options.builder,
                                    options.os, options.tester, options.bits,
                                    options.version):
    print subordinate
  return 0


if __name__ == '__main__':
  sys.exit(Main())
