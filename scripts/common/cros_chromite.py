#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module wraps ChromeOS's Chromite configuration, providing retrieval
methods and Infra-aware introspection.

For any given ChromeOS build, Chromite may be pinned to a specific ChromeOS
branch or unpinned at tip-of-tree. Consequently, one function of this module
is to version Chromite and allow external scripts to retrieve a specific
version of its configuration.

This file may also be run as a standalone executable to synchronize the pinned
configurations in a cache directory.
"""

import argparse
import base64
import collections
import json
import logging
import os
import sys

try:
  import requests
  import requests.exceptions
except ImportError:
  # TODO(dnj): Remove me.
  #
  # crbug.com/452528: Inconsistent PYTHONPATH environments sometimes cause
  # subordinates.cfg (and thus this file) to be parsed without 'third_party/requests'
  # present. We will add logic to gracefully become read-only when 'requests'
  # is missing so bots don't show errors.
  requests = None

# Add 'common' to our path.
from common import configcache, env

# The name of the branch associated with tip-of-tree.
TOT_BRANCH = 'main'


# Configure our pin locations. Because repository availability is dependent
# on checkout layout, pin descriptors are conditional on their repository's
# availability.
#
# These are maintained via a DEPS hook in <build>/DEPS. In order to update a
# pinned revision:
# - Update the value in the respective JSON file.
# - Run "gclient runhooks --force".
PIN_JSON_PATH = os.path.join(env.Build, 'scripts', 'common',
                             'cros_chromite_pins.json')


class ChromiteError(RuntimeError):
  pass


# Subordinate pool allocation types. This mirrors the VALID_BUILD_SLAVE_TYPES in:
# https://chromium.googlesource.com/chromiumos/chromite/+/master/cbuildbot/constants.py
class SubordinateType(object):
  """Subordinate configuration expression enumeration."""
  BAREMETAL = 'baremetal'
  VM = 'vm'
  GCE = 'gce'
  GCE_WIMPY = 'gce_wimpy'
  GCE_BEEFY = 'gce_beefy'


class ChromiteTarget(object):
  """Wraps a single Chromite target.

  Reproduces some core logic from Chromite's 'cbuildbot' libraries to access
  various configuration parameters.
  """

  ANDROID_PFQ = 'android_pfq'
  ASAN = 'asan'
  CANARY = 'canary'
  FACTORY = 'factory'
  FIRMWARE = 'firmware'
  FULL = 'full'
  INCREMENTAL = 'incremental'
  PALADIN = 'paladin'
  PFQ = 'pfq'
  PRE_CQ = 'pre-cq'
  PRE_CQ_LAUNCHER = 'pre-cq-launcher'
  PRE_FLIGHT_BRANCH = 'pre-flight-branch'
  REFRESH_PACKAGES = 'refresh-packages'
  SDK = 'sdk'
  TOOLCHAIN = 'toolchain'

  # Maps cbuildbot's "build_type" field to target constants. This is used in the
  # first pass prior to attempting to infer the class from the target's name.
  # (see Categorize)
  BUILD_TYPE_CATEGORY_MAP = {
    'priest': PRE_CQ_LAUNCHER,
    'paladin': PALADIN,
    'canary': CANARY,
    'chrome': PFQ,
  }

  BUILDER_NAME_CATEGORY_MAP = {
    'refresh-packages': REFRESH_PACKAGES,
  }

  # Maps configuration name suffixes to target type constants.
  # (see Categorize)
  SUFFIX_MAP = collections.OrderedDict((
    (ANDROID_PFQ, ('android-pfq',)),
    (ASAN, ('asan',)),
    (CANARY, ('release', 'release-group',)),
    (FACTORY, ('factory',)),
    (FIRMWARE, ('firmware',)),
    (FULL, ('full',)),
    (INCREMENTAL, ('incremental',)),
    (PALADIN, ('paladin',)),
    (PFQ, ('chrome-pfq', 'chromium-pfq',)),
    (PRE_CQ, ('pre-cq',)),
    (PRE_FLIGHT_BRANCH, ('pre-flight-branch',)),
    (SDK, ('sdk',)),
    (TOOLCHAIN, ('toolchain', 'toolchain-group', 'toolchain-major',
                 'toolchain-minor',)),
  ))

  # Sentinel value to indicate a missing key.
  _MISSING = object()

  def __init__(self, name, config, default=None, templates=None):
    self._name = name
    self._config = config
    self._children = ()
    template = config.get('_template')
    if templates and template and default:
      default = default.copy()
      default.update(templates.get(template, {}))
    self._default = default
    self._base, self._suffix, self._category = self.Categorize(
        name,
        build_type=self.get('build_type'))

  def _setChildren(self, children):
    self._children = tuple(children)

  @classmethod
  def FromConfigDict(cls, name, config, default=None, templates=None):
    """Returns: (ChromiteTarget) A target instance parsed from a config dict.
    """
    result = cls(name, config, default=default, templates=templates)

    # Wrap and add any child configurations in ChromiteTarget instances.
    #
    # As of 231348146015739254fd2978dd172975555e9bdc, Chromite uses the common
    # default dictionary for all children.
    result._setChildren(tuple(cls.FromConfigDict(None, child, default=default,
                                                 templates=templates)
                              for child in config.get('child_configs', ())))

    return result

  @property
  def name(self):
    """Returns: (str) The target's name. This may be None for child targets.
    """
    return str(self._name)

  @property
  def board(self):
    boards = self.get('boards')
    if not boards or len(boards) != 1:
      return None
    return str(boards[0])

  @property
  def base(self):
    """Returns: (str) The base board name."""
    return str(self._base)

  @property
  def suffix(self):
    """Returns: (str) The base board name."""
    return str(self._suffix)

  @property
  def category(self):
    """Returns: (enum) A category enumeration based on the name or None.
    """
    return self._category

  @property
  def is_main(self):
    return self['main']

  @property
  def is_public(self):
    return (
        self.get('prebuilts') == 'public' and
        not self.is_main)

  @property
  def children(self):
    """Returns: tuple(ChromiteTarget) a tuple of child target configurations.
    """
    return self._children

  def __getitem__(self, key):
    value = self.get(key, self._MISSING)
    if value is self._MISSING:
      raise KeyError(key)
    return value

  def get(self, key, default=None):
    """Returns: The configuration item associated with the key.

    This method retrieves a configuration item first by checking the target's
    configuration dictionary, then by falling back to the configured default
    dictionary.

    Args:
      key: (str) The key to retrieve.
      default: If supplied, the value that will be returned if the key is
          missing.
    """
    value = self._config.get(key, self._MISSING)
    if value is not self._MISSING:
      return value
    if self._default:
      value = self._default.get(key, self._MISSING)
      if value is not self._MISSING:
        return value
    return default

  def _HasTests(self, test_property):
    if self.get(test_property):
      return True
    for child in self.children:
      if child._HasTests(test_property):
        return True
    return False

  def HasVmTests(self):
    """Returns: (bool) if this target or any of its children have VM tests.
    """
    return self._HasTests('vm_tests')

  def HasHwTests(self):
    """Returns: (bool) if this target or any of its children have VM tests.
    """
    return self._HasTests('hw_tests')

  def HasUnitTests(self):
    """Returns: (bool) if this target or any of its children have unit tests.
    """
    return self._HasTests('unittests')

  def IsGeneralPreCqBuilder(self):
    return self.name == 'pre-cq-group'

  def IsPreCqBuilder(self):
    return self.IsGeneralPreCqBuilder() or self.category == self.PRE_CQ

  @classmethod
  def Categorize(cls, name, build_type=None):
    """Returns: (base, suffix, typ)
      base: (str) The base board name
      suffix: (str) The board type suffix, if identifed. Otherwise, None.
      category: (enum) The config typecategory if identified. Otherwise, None.

    This method attempts to identify the type of build based on the build name.
    If no type can be inferred, None will be returned.

    Args:
      name (str): The configuration name.
      build_type (str): If not None, the configuration build type.
    """
    name = name or ''

    category = cls.BUILDER_NAME_CATEGORY_MAP.get(name)
    if not category and build_type:
      category = cls.BUILD_TYPE_CATEGORY_MAP.get(build_type)

    if not category:
      # Attempt to infer the category from the name.
      def get_category():
        for typ, suffixes in cls.SUFFIX_MAP.iteritems():
          for suffix in suffixes:
            if name.endswith('-' + suffix):
              return typ
        return None
      category = get_category()

    # If we couldn't categorize, fail.
    if not category:
      return None, None, None

    # Split any suffix.
    suffixes = cls.SUFFIX_MAP.get(category, ())
    for suffix in suffixes:
      if name.endswith('-' + suffix):
        return name[:-(len(suffix)+1)], suffix, category
    return name, None, category


class ChromiteConfig(collections.OrderedDict):
  """Wraps a full Chromite configuration dictionary."""

  def __init__(self, default_config=None, templates=None, site_params=None):
    super(ChromiteConfig, self).__init__(self)
    self._default = default_config or {}
    self._templates = templates
    self._site_params = site_params

  def AddTarget(self, name, config):
    """Adds a named Chromite target to the config object.

    Args:
        name: (str) The name of the target.
        config: (dict) The target's configuration dictionary.

    Returns: (ChromiteTarget) The generated ChromiteTarget object.
    """
    assert not self.get(name), ('Target [%s] is already registered.' % (name,))
    self[name] = target = ChromiteTarget.FromConfigDict(
        name, config, default=self._default, templates=self._templates)
    return target

  @classmethod
  def FromConfigDict(cls, config):
    """Returns: (ChromiteConfig) instantiates from a string containing JSON.

    Raises:
      ValueError: If the JSON string could not be parsed.
    """
    config = config.copy()
    default = config.pop('_default', None)
    templates = config.pop('_templates', None)
    site_params = config.pop('_site_params', None)
    chromite_config = cls(default, templates, site_params)
    for k, v in config.iteritems():
      chromite_config.AddTarget(k, v)
    return chromite_config


class ChromitePinManager(object):
  """Manages Chromite pinning associations."""

  def __init__(self, cache_name, pinned, require=False):
    """Instantiates a new ChromitePinManager.

    Args:
      pinned: (dict) A dictionary of [branch-name] => [pinned revision] for
          pinned branch lookup.
      require: (bool) If False, a requested branch without a pinned match will
          return that branch name; otherwise, a ChromiteError will be returned.
    """
    self._cache_name = cache_name
    self._pinned = pinned
    self._require = require

  @property
  def cache_name(self):
    return self._cache_name

  @classmethod
  def LoadFromJSON(cls, cache_name, path, **kwargs):
    """Returns: (ChromitePinManager) a ChromitePinManager instance.

    Loads a ChromitePinManager configuration from a pin JSON file.
    """
    logging.debug('Loading default pins from: %s', path)
    with open(path, 'r') as fd:
      pins = json.load(fd)
    if not isinstance(pins, dict):
      raise TypeError('JSON pins are not a dictionary: %s' % (path,))
    return cls(cache_name, pins, **kwargs)

  def iterpins(self):
    """Returns: an iterator over registered (pin, commit) tuples."""
    return self._pinned.iteritems()

  def GetPinnedBranch(self, branch):
    """Returns: (str) the pinned version for a given branch, if available.

    Args:
      branch: The pinned branch name to retrieve.

    This method will return the pinned version of a given branch name. If no
    pin for that branch is registered, the branch will be used directly.
    """
    value = self._pinned.get(branch)
    if not value:
      if self._require:
        raise ChromiteError('No pinned Chromite commit for [%s]' % (
              branch,))
      value = branch
    return value

  def Get(self, branch=None, allow_fetch=True):
    """Returns: (ChromiteConfig) the Chromite configuration for a given branch.

    Args:
      branch: (str) The name of the branch to retrieve. If None, use
          tip-of-tree.
      allow_fetch: (bool) If True, allow a Get miss to fetch a new cache value.
    """
    cache_manager = _GetCacheManager(
        self,
        allow_fetch=allow_fetch)

    try:
      _UpdateCache(cache_manager, self)
    except configcache.ReadOnlyError as e:
      raise ChromiteError("Cannot update read-only config cache. Run "
                          "`gclient runhooks --force`: %s" % (e,))

    return ChromiteConfigManager(
        cache_manager,
        pinned=self,
    ).GetConfig(branch)

  def List(self):
    """Returns: (list) a list of the configured Chromite pin branch names."""
    return self._pinned.keys()


class ChromiteConfigManager(object):
  """Manages Chromite configuration options and Chromite config fetching."""

  def __init__(self, cache_manager, pinned=None):
    """Instantiates a new ChromiteConfigManager instance.

    Args:
      cache_manager: (cachemanager.CacheManager) The cache manager to use.
      pinned: (ChromitePinManager) If not None, the pin manager to use to lookup
          pinned branches. Otherwise, the branches will be used directly.
    """
    self._cache_manager = cache_manager
    self._pinned = pinned

  def GetConfig(self, branch):
    """Returns: (ChromiteConfig) the configured Chromite configuration.

    Args:
      branch: (str) The Chromite branch. If None, use tip-of-tree.

    Rasies:
      ChromiteError: if there was an error retrieving the configuration.
    """
    branch = branch or TOT_BRANCH
    req_branch = (self._pinned.GetPinnedBranch(branch) if self._pinned
                                                       else branch)
    config = self._cache_manager.Get(branch, req_branch)
    if not config:
      raise ChromiteError("No cached configuration for branch '%s'." % (
          branch,))
    try:
      config = json.loads(config)
    except ValueError as e:
      raise ChromiteError('Failed to parse config JSON for %s: %s' % (
          req_branch, e,))

    # The configuration is expected to be a dictionary of config=>config-dict.
    if not isinstance(config, dict):
      raise ChromiteError('JSON object for %s is not a dictionary (%s)' % (
          req_branch, type(config).__name__),)

    config = ChromiteConfig.FromConfigDict(config)
    return config


class GitilesError(configcache.FetcherError):
  """A RuntimeError raised for failures attributed to Gitiles."""
  def __init__(self, url, message=None):
    super(GitilesError, self).__init__('[%s]: %s' % (url, message))
    self.url = url


class ChromiteFetcher(object):
  """Callable ConfigCache fetch function for Chromite config artifacts."""

  CHROMITE_GITILES_BASE = (
      'https://chromium.googlesource.com/chromiumos/chromite')
  CHROMITE_CONFIG_PATH = 'cbuildbot/config_dump.json'

  def __init__(self, pin_manager):
    self._pinned = pin_manager

  def _GetText(self, url):
    """Returns: (str) The text content from a URL.

    Raises:
      GitilesError: If there was an unexpected failure with the Gitiles service.
    """
    logging.warning('Loading Chromite configuration from: %s', url)

    try:
      # Force no authentication. Chromite is public! By default, 'requests' will
      # use 'netrc' for authentication. This can cause the load to fail if
      # the '.netrc' has an invalid entry, failing authentication.
      return requests.get(
          url,
          verify=True,
          auth=lambda r: r).text
    except requests.exceptions.RequestException as e:
      raise GitilesError(url, 'Request raised exception: %s' % (e,))

  def __call__(self, name, version):
    """Returns: (str) the contents of a specified file from Gitiles.

    Args:
      name: (str) The artifact name. In this case, it's the pinned branch.
      version: (str) The requested version. In this case, it's a Git commit.
          If None, the pinned Git commit of the 'name' branch will be used.

    Raises:
      GitilesError: If there was an unexpected failure with the Gitiles service.
    """
    if not version:
      version = self._pinned.GetPinnedBranch(name)
    url = '%s/+/%s/%s?format=text' % (
        self.CHROMITE_GITILES_BASE,
        version,
        self.CHROMITE_CONFIG_PATH)
    data = self._GetText(url)
    try:
      data = base64.b64decode(data)
    except (TypeError, UnicodeEncodeError) as e:
      raise GitilesError(url, 'Failed to decode Base64: %s' % (e,))
    return data, version


# Default ChromitePinManager instance.
_DEFAULT_PIN_MANAGER = None
def DefaultChromitePinManager():
  global _DEFAULT_PIN_MANAGER
  if not _DEFAULT_PIN_MANAGER:
    _DEFAULT_PIN_MANAGER = ChromitePinManager.LoadFromJSON('chromite',
                                                           PIN_JSON_PATH)
  return _DEFAULT_PIN_MANAGER


def Get(branch=None, allow_fetch=True):
  """Returns: (ChromiteConfig) the Chromite configuration for a given branch.

  Args:
    branch: (str) The name of the branch to retrieve. If None, use tip-of-tree.
    allow_fetch: (bool) If True, allow a Get miss to fetch a new cache value.
  """
  return DefaultChromitePinManager().Get(
      branch=branch,
      allow_fetch=allow_fetch)


def List():
  """Returns: (list) a list of the configured Chromite pin branch names."""
  return DefaultChromitePinManager().List()


def _UpdateCache(cache_manager, pin_manager, force=False):
  """Fetches all default pinned versions.

  Args:
    cache_manager: (configcache.CacheManager) The cache manager to use.
    pin_manager: (ChromitePinManager) The pin manager to use.
    force: (bool) If True, reload the entire cache instead of performing an
        incremental update.
  """
  updated = []
  for artifact, version in pin_manager.iterpins():
    if force:
      cache_manager.FetchAndCache(artifact, version)
      updated.append(artifact)
    else:
      data = cache_manager.Get(artifact, version=version)
      if data is None:
        logging.info("Fetching artifact '%s', version '%s'.",
            artifact, version)
        cache_manager.FetchAndCache(artifact)
        updated.append(artifact)
  return updated


def _GetCacheManager(pin_manager, allow_fetch=False, **kwargs):
  """Returns: (CacheManager) A CacheManager instance.

  This function will return a configured CacheManager instance. If 'allow_fetch'
  is None or if the 'requests' module could not be imported (crbug.com/452528),
  the returned CacheManager will be read-only (i.e., no ChromiteFetcher).

  Args:
    pin_manager: The ChromitePinManager to use.
  """
  return configcache.CacheManager(
      pin_manager.cache_name,
      # TODO(dnj): Remove the 'requests' test (crbug.com/452258).
      fetcher=(ChromiteFetcher(pin_manager) if allow_fetch and requests
                                            else None),
      **kwargs)


def main(argv, pin_manager_gen):
  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose', action='count', default=0,
      help='Increase process verbosity. This can be specified multiple times.')
  parser.add_argument('-D', '--cache-directory',
      help='The base cache directory to download pinned configurations into.')
  parser.add_argument('-f', '--force', action='store_true',
      help='Forces an update, even if the cached already contains an artifact.')
  args = parser.parse_args(argv)

  # Handle verbosity.
  if args.verbose == 0:
    loglevel = logging.WARNING
  elif args.verbose == 1:
    loglevel = logging.INFO
  else:
    loglevel = logging.DEBUG
  logging.getLogger().setLevel(loglevel)

  pm = pin_manager_gen()
  cm = _GetCacheManager(pm, allow_fetch=True, cache_dir=args.cache_directory)
  updated = _UpdateCache(cm, pm, force=args.force)
  logging.info('Updated %d cache artifact(s).', len(updated))
  return 0


# Allow this script to be used as a bootstrap to fetch/cache Chromite
# artifacts (gclient runhooks).
if __name__ == '__main__':
  logging.basicConfig()
  try:
    sys.exit(main(sys.argv[1:], DefaultChromitePinManager))
  except Exception as e:
    logging.exception("Uncaught execption: %s", e)
  sys.exit(1)
