# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

class LuciConfigApi(recipe_api.RecipeApi):
  def get_projects(self):
    """Fetch the mapping of project id to url from luci-config.

    Returns:
      A dictionary mapping project id to its luci-config project spec (among
      which there is a repo_url key).
    """
    # TODO(phajdan.jr): switch to fetch recipe module.
    # When we start passing auth token e.g. for internal projects,
    # it'd be better not to leak it, even on internal-only builders.
    cmd = ['curl', 'https://luci-config.appspot.com/_ah/api/config/v1/projects']
    fetch_result = self.m.step('Get project urls',
        cmd,
        stdout=self.m.json.output(),
        step_test_data=lambda: self.m.json.test_api.output_stream({
               'projects': [
                   {
                       'repo_type': 'GITILES',
                       'id': 'recipe_engine',
                       'repo_url': 'https://repo.repo/recipes-py',
                   },
                   {
                       'repo_type': 'GITILES',
                       'id': 'build',
                       'repo_url': 'https://repo.repo/chromium/build',
                   }
               ],
           }))
    mapping = {}
    for project in fetch_result.stdout['projects']:
      mapping[project['id']] = project
    return mapping
