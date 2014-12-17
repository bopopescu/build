# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common steps for recipes that use repo for source control."""

import os

from slave import recipe_api

class RepoApi(recipe_api.RecipeApi):
  """Provides methods to encapsulate repo operations."""
  # WARNING: The version of repo checked into depot_tools doesn't support
  # switching between branches correctly due to
  # https://code.google.com/p/git-repo/issues/detail?id=46

  def __init__(self, **kwargs):
    super(RepoApi, self).__init__(**kwargs)
    self._repo_path = None

  @property
  def repo_path(self):
    if not self._repo_path:
      self._repo_path = self.m.path['depot_tools'].join('repo')
    return self._repo_path

  @repo_path.setter
  def repo_path(self, path):
    self._repo_path = path

  def init(self, url, *args, **kwargs):
    """Perform a 'repo init' step with the given manifest url."""
    kwargs.setdefault('infra_step', True)
    return self.m.step('repo init',
                       [self.repo_path, 'init', '-u', url] + list(args),
                       **kwargs)

  def sync(self, *args, **kwargs):
    """Sync an already-init'd repo."""
    # NOTE: This does not set self.m.path['checkout']
    kwargs.setdefault('infra_step', True)
    suffix = kwargs.pop('suffix', None)
    name = 'repo sync'
    if suffix:
      name += ' - ' + suffix
    return self.m.step(name,
                       [self.repo_path, 'sync'] + list(args),
                       **kwargs)

  def clean(self, *args, **kwargs):
    """Clean an already-init'd repo."""
    kwargs.setdefault('infra_step', True)
    return self.m.step('repo forall git clean',
                       [self.repo_path, 'forall', '-c', 'git', 'clean',
                        '-f', '-d'] + list(args),
                       **kwargs)

  def reset(self, **kwargs):
    """Reset to HEAD an already-init'd repo."""
    return self.m.step('repo forall git reset',
                       [self.repo_path, 'forall', '-c', 'git', 'reset',
                        '--hard', 'HEAD'],
                       **kwargs)
