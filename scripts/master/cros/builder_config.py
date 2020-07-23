# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility classes to define and coordinate CrOS Chromite builder display.
"""

import re

from collections import OrderedDict, namedtuple

from common.cros_chromite import ChromiteTarget, SubordinateType


class _AnnotatedCallable(object):
  """Annotated callable that has a friendly string message for
  config/expectation dumps."""

  def __init__(self, func, doc):
    self._func = func
    self._doc = doc

  def __repr__(self):
    return self._doc

  def __call__(self, *args, **kwargs):
    return self._func(*args, **kwargs)


# BuildBot builder 'collapseRequests' callable that always returns True.
# (See http://docs.buildbot.net/latest/manual/customization.html)
AlwaysCollapseFunc = _AnnotatedCallable(
    lambda _req1, _req2: True,
    '<Always Collapse>')


class BuilderConfig(object):
  """Represents the presentation of a Chromite builder on a waterfall.

  Note that every property here is potentially derivable from the Chromite
  configuration. Information stored in this class should be examined in detail
  and, as appropriate, moved into Chromite.
  """

  # Default set of class base properties. Subclasses can override these to
  # affect behavior.
  CLOSER = False
  FLOATING = None
  UNIQUE = False
  COLLAPSE = True
  SLAVE_TYPE = SubordinateType.BAREMETAL
  CBB_VARIANT = None
  TIMEOUT = None

  def __init__(self, config, branch=None):
    """Initializes a new configuration.

    Args:
      config (ChromiteTarget): The underlying Chromite configuration object.
    """
    self.config = config
    self.branch = branch

  def __repr__(self):
    return '%s/%s' % (self.config.name, self.config.category)

  def __cmp__(self, other):
    assert isinstance(other, BuilderConfig)
    return cmp(self._CmpTuple(), other._CmpTuple())

  def _CmpTuple(self):
    """Returns (tuple): A comparable tuple to determine waterfall ordering."""
    return (self.ordinal, not self.config.is_main, self.is_experimental,
            self.config.name)

  @property
  def closer(self):
    """Returns (bool): Whether or not this builder is a tree closer."""
    return self.CLOSER

  @property
  def subordinate_type(self):
    """Returns (str): A SubordinateType enumeration value."""
    return self.config.get('buildsubordinate_type', self._GetLegacySubordinateType())

  @property
  def cbb_variant(self):
    """Returns (str): Cbuildbot recipe variant for this builder type, or None.
    """
    variant = self.config.category
    if variant and self.config.is_main:
      return '%s-main' % (variant,)
    return variant

  @property
  def timeout(self):
    """Returns (int/None): This builder type's custom build timeout value.
    """
    return self.TIMEOUT

  @property
  def unique(self):
    """Returns (bool): Whether BuildBot should enforce singleton locks."""
    return self.UNIQUE

  @property
  def collapse(self):
    """Returns (bool): Whether BuildBot should collapse multiple builds.

    This will be passed to the 'collapseRequests' builder property, and can
    either be True, False, or a lambda function (see
    http://docs.buildbot.net/latest/manual/customization.html).
    """
    return self.COLLAPSE

  @property
  def floating(self):
    """Returns (bool): Whether this builder should have a floating backup subordinate.
    """
    return self.FLOATING

  @property
  def ordinal(self):
    """Returns (int): This builder's ordinal (sort order).

    This BuilderConfig class' ordinal. This is determined by its position in the
    CONFIG_MAP.
    """
    result = ORDINALS.get(self.config.category)
    if result is None:
      return ORDINALS.get(None)
    return result

  @property
  def builder_name(self):
    """Returns (str): The waterfall builder name for this configuration."""
    if self.config.get('buildbot_waterfall_name'):
      return self.config['buildbot_waterfall_name']
    return str(self._GetBuilderName())

  @property
  def is_experimental(self):
    """Returns (bool): If this builder is experimental."""
    return self._IsExperimental()

  def _GetBuilderName(self):
    """Returns (str): Returns the generated builder name.

    Unless overloaded, the builder name will default to the target configuration
    name.
    """
    return self.config.name

  def _GetLegacySubordinateType(self):
    """Returns (str): Returns the generated builder name.

    Unless overloaded, the builder name will default to the target configuration
    name.

    TODO(dnj): Deprecate this when release waterfall no longer uses old Chromite
               configurations that don't supply the 'buildsubordinate_type' parameter.
    """
    return self.SLAVE_TYPE

  def _IsExperimental(self):
    """Returns (bool): If this builder is experimental.

    Unless overloaded, a builder is experimental if it's not a main builder or
    important.
    """
    return not (self.config.is_main or self.config.get('important'))


class PreCqLauncherBuilderConfig(BuilderConfig):
  """BuilderConfig for the Pre-CQ launcher target."""

  UNIQUE = True
  CLOSER = True
  SLAVE_TYPE = SubordinateType.GCE_WIMPY


class PaladinBuilderConfig(BuilderConfig):
  """BuilderConfig for Paladin launcher targets."""

  UNIQUE = True
  FLOATING = 'paladin'


class IncrementalBuilderConfig(BuilderConfig):
  """BuilderConfig for Incremental launcher targets."""

  CLOSER = True
  COLLAPSE = AlwaysCollapseFunc

  def _IsExperimental(self):
    return False


class FullBuilderConfig(BuilderConfig):
  """BuilderConfig for Full launcher targets."""

  CLOSER = True
  COLLAPSE = AlwaysCollapseFunc

  def _IsExperimental(self):
    return False


class AsanBuilderConfig(BuilderConfig):
  """BuilderConfig for ASAN launcher targets."""

  CLOSER = True
  COLLAPSE = AlwaysCollapseFunc

  def _IsExperimental(self):
    return False


class CanaryBuilderConfig(BuilderConfig):
  """BuilderConfig for canary/release launcher targets."""

  def _GetLegacySubordinateType(self):
    if self.config.is_main and not self.config['boards']:
      # For boardless release mains, use a wimpy builder.
      #
      # NOTE: Currently only implemented on release branch.
      if self.branch:
        return SubordinateType.GCE_WIMPY
    return SubordinateType.BAREMETAL


class SdkBuilderConfig(BuilderConfig):
  """BuilderConfig for SDK launcher targets."""

  SLAVE_TYPE = SubordinateType.GCE
  COLLAPSE = AlwaysCollapseFunc
  TIMEOUT = 22 * 3600 # 22 Hours.

  def _IsExperimental(self):
    return False


class ToolchainBuilderConfig(BuilderConfig):
  """BuilderConfig for toolchain launcher targets.

  Toolchain builders leverage a declared subordinate class to share subordinates between
  them.
  """

  def _GetLegacySubordinateType(self):
    if self.config.is_main and not self.config['boards']:
      return SubordinateType.GCE_WIMPY
    return SubordinateType.BAREMETAL


# Map of cbuildbot target type to configuration class.
#
# This is an ordered dictionary. The order of items corresponds to the
# config type's order on the waterfall.
#
# Any configuration type not mapped should default to the 'None' value.
CONFIG_MAP = OrderedDict((
    (ChromiteTarget.PRE_CQ_LAUNCHER, PreCqLauncherBuilderConfig),
    (ChromiteTarget.PALADIN, PaladinBuilderConfig),
    (ChromiteTarget.INCREMENTAL, IncrementalBuilderConfig),
    (ChromiteTarget.FULL, FullBuilderConfig),
    (ChromiteTarget.ASAN, AsanBuilderConfig),
    (ChromiteTarget.FIRMWARE, BuilderConfig),
    (ChromiteTarget.PFQ, BuilderConfig),
    (ChromiteTarget.PRE_FLIGHT_BRANCH, BuilderConfig),
    (ChromiteTarget.CANARY, CanaryBuilderConfig),
    (ChromiteTarget.SDK, SdkBuilderConfig),
    (ChromiteTarget.TOOLCHAIN, ToolchainBuilderConfig),
    (ChromiteTarget.ANDROID_PFQ, BuilderConfig),
    (None, BuilderConfig),
))

# Determine ordinals for each BuilderTarget type.
_config_map_keys = CONFIG_MAP.keys()
ORDINALS = dict((k, _config_map_keys.index(k))
                for k in CONFIG_MAP.iterkeys())


def GetBuilderConfig(target, **kwargs):
  """Returns (BuilderConfig): a typed BuilderConfig instance for a target.

  Args:
    target (ChromiteTarget): The Chromite target to configure.
  """
  return CONFIG_MAP.get(target.category, CONFIG_MAP[None])(target, **kwargs)


def GetBuilderConfigs(targets, **kwargs):
  """Returns (OrderedDict): BuilderConfig instances for a set of targets.

  Args:
    targets (list): A list of ChromiteTarget instances to generate
        BuilderConfigs for.
  """
  configs = [GetBuilderConfig(t, **kwargs)
             for t in targets.itervalues()]
  configs.sort()
  return OrderedDict((c.config.name, c) for c in configs)


def IsGCESubordinate(subordinatename):
  """Returns (bool): Whether |subordinatename| is hosted on GCE.

  Args:
    subordinatename: The hostname of the subordinate.
  """
  # The "-c2" suffix indicates that a builder is in GCE (as opposed to
  # in the Chrome Golo, which has a -m2 suffix).
  return bool(re.search(r'-c\d+$', subordinatename))
