# -*- python -*-
# ex: set syntax=python:

# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib

from common import cros_chromite
from main.cros import builder_config

# Load all of Chromite's 'cbuildbot' config targets from ToT.
# NOTE: This uses a pinned Chromite configuration. To update the Chromite
#       configuration and, thorugh it, the main configuration, the pinned
#       hash should be updated in "<build>/scripts/common/cros_chromite.py".
#       (See cros_chromite.PINS documentation).
# TODO(dnj): We allow fetching here because neither the CQ nor mains will run
#            `gclient runhooks` automatically. I'd prefer it not do this so
#            main restarts are deterministic and fast. However, since the
#            loaded configuration is pinned and cached, this shouldn't have a
#            significant impact in practice.
configs = cros_chromite.Get()

# Load builder sets from the 'cbuildbot' config.
cbb_builders = set(v['_template'] or k for k, v in configs.iteritems())
etc_builders = set(['etc'])
all_builders = cbb_builders.union(etc_builders)

# Build a list of configs that contain at least one non-VMTest, non-HWTest
# Pre-CQ builder. This is used for determining a list of configs that could
# theoretically run on GCE (we check this for sure in NextSubordinateAndBuild).
precq_builders = set(
    v['_template'] or k for k, v in configs.iteritems() if v.IsPreCqBuilder())
precq_novmtest_builders = set(
    v['_template'] or k for k, v in configs.iteritems()
    if v.IsPreCqBuilder() and not v.HasVmTests() and not v.HasHwTests())


class TestingSubordinatePool(object):

  def __init__(self, testing_subordinates=None):
    self.testing_subordinates = set(testing_subordinates or ())

  def is_testing_subordinate(self, subordinatename):
    return subordinatename in self.testing_subordinates

  def cros_subordinate_name(self, subordinatename):
    """BuildBot Jinja2 template function to style our subordinate groups into pools.

    This function is called by our customized 'buildsubordinates.html' template. Given
    a subordinate name, it returns the name to display for that subordinate.
    """
    if self.is_testing_subordinate(subordinatename):
      return '%s (Testing)' % (subordinatename,)
    return subordinatename


def cros_builder_links_pool(name, builders):
  """Returns a builder list for a pool, summarizing multiple builders in a
  single entry (see cros_builder_links).

  Args:
    name: The name of the pool.
    builders: The builders that compose the pool.

  Returns:
    A builder list (see cros_builder_links for description).
  """

  query = '&'.join('builder=%s' % (urllib.quote(n),)
                   for n in sorted(builders))
  return [{'link': 'builders?%s' % (query,), 'name': name}]


def cros_builder_links(builders):
  """BuildBot Jinja2 template function to style our subordinate groups into pools.

  This function is called by our customized 'buildsubordinates.html' template. It is
  evaluated for each subordinate, receiving 'builders', a list containing template
  information for each builder attached to that subordinate.

  This function accepts and returns a list containing entries:
    {'name': <name>, 'link': <link>}

  Each entry is then used by the templating engine to populate that subordinate's
  builder table cell. This function analyzes the list of builders for a
  given subordinate and optionally returns a modified set of links to render.

  This function summarizes known sets of builders, replacing individual builder
  names/links with concise builder pool names/links.
  """
  builder_names = set(s['name'] for s in builders)

  if builder_names == all_builders:
    return [{'link': 'builders', 'name': 'General'}]
  elif builder_names == precq_builders:
    return cros_builder_links_pool('Pre-CQ', precq_builders)
  elif builder_names == precq_novmtest_builders:
    return cros_builder_links_pool('Pre-CQ (GCE)',
                                   precq_novmtest_builders)
  return builders


class NextSubordinateAndBuild(object):
  """Callable BuildBot 'nextSubordinateAndBuild' function for ChromeOS try server.

  This function differs from default assignment:
  - It preferentially assigns subordinates to builds that explicitly request subordinates.
  - It prioritizes higher-strata builders when multiple builders are asking
    for subordinates.
  - It prioritizes subordinates with fewer builders (more specialized) over subordinates
    with more builders.
  """

  def __init__(self, testing_subordinate_pool=None):
    """Initializes a new callable object.

    Args:
      testing_subordinate_pool (None/TestingSubordinatePool): If not None, the pool of
          testing subordinates.
    """
    self.testing_subordinate_pool = testing_subordinate_pool or TestingSubordinatePool()

  @staticmethod
  def get_buildrequest_category(br):
    """Returns (str): the category of builder associated with a build request.
    """
    builder = br.main.status.getBuilder(br.buildername)
    if not builder:
      return None
    return builder.category

  # Paraphrased from 'buildbot.status.web.subordinates.content()'.
  @staticmethod
  def get_subordinate_builders(subordinate, br):
    """Returns (list): The names (str) of builders assigned to a subordinate.
    """
    builders = []
    for bname in br.main.status.getBuilderNames():
      b = br.main.status.getBuilder(bname)
      for bs in b.getSubordinates():
        if bs.getName() == subordinate.subordinatename:
          builders.append(b)
    return builders

  def is_testing_subordinate(self, subordinate):
    """Returns: True if 'subordinate' is a testing subordinate.

    Args:
      subordinate (BuildSubordinate): The build subordinate to test.
    """
    return self.testing_subordinate_pool.is_testing_subordinate(subordinate.subordinatename)

  def FilterSubordinates(self, cbb_config, subordinates):
    """Filters |subordinates| to only contain valid subordinates for |cbb_config|.

    Args:
      cbb_config (ChromiteTarget): The config to filter for.
      subordinates: List of BuildSubordinate objects to filter to filter.
    """
    if (not cbb_config or cbb_config.HasVmTests() or
        cbb_config.HasHwTests()):
      subordinates = [s for s in subordinates if not builder_config.IsGCESubordinate(s.getName())]
    return subordinates

  def __call__(self, subordinates, buildrequests):
    """Called by main to determine which job to run and which subordinate to use.

    Build requests may have a 'subordinates_request' property (list of strings),
    established from the try job definition. Such requests allow try jobs to
    request to be run on specific subordinates.

    Arguments:
      subordinates: A list of candidate SubordinateBuilder objects.
      buildrequests: A list of pending BuildRequest objects.

    Returns:
      A (subordinate, buildrequest) tuple containing the buildrequest to run and
      the subordinate to run it on.
    """
    # We need to return back a BuilderSubordinate object, so map subordinate names to
    # BuilderSubordinate objects.
    subordinate_dict = dict((bs.subordinate.subordinatename, bs) for bs in subordinates)

    # Service builds with explicit subordinate requests first. A build requesting a
    # specific set of subordinates will only be scheduled on those subordinates.
    remaining = []
    for br in buildrequests:
      subordinates_request = br.properties.getProperty('subordinates_request', None)
      if not subordinates_request:
        remaining.append(br)
        continue

      # If a list of subordinates are requested, the order of the list is the order
      # of preference.
      for subordinate_name in subordinates_request:
        s = subordinate_dict.get(subordinate_name)
        if s:
          return s, br

    # Service builds based on priority. We will use a builder's 'category' as
    # its priority, which also mirrors waterfall ordering.
    #
    # Note: Python sort is stable, so this will preserve the relative order of
    # build requests that share a category.
    remaining.sort(key=self.get_buildrequest_category)

    # Get a list of available subordinates. We'll sort ascendingly by number of
    # attached builders with the intention of using more-specialized (fewer
    # attached builders) subordinates before using generic ones.
    normal_subordinates = [s for s in subordinates
                     if not self.is_testing_subordinate(s.subordinate)]

    for br in remaining:
      normal_subordinates.sort(key=lambda s:
          -int(builder_config.IsGCESubordinate(s.subordinate.subordinatename)))

      # Iterate through subordinates and choose the appropriate one.
      cbb_config_name = br.properties.getProperty('cbb_config', None)
      cbb_config = configs.get(cbb_config_name)
      builder = br.main.status.getBuilder(br.buildername)
      subordinates = self.FilterSubordinates(cbb_config, builder.getSubordinates())
      for s in normal_subordinates:
        for builder_subordinate in subordinates:
          if s.subordinate.subordinatename == builder_subordinate.getName():
            return s, br
    return None, None
