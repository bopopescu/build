# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class RecipeAutorollerApi(recipe_api.RecipeApi):
  def prepare_checkout(self):
    """Creates a default checkout for the recipe autoroller."""
    self.m.gclient.set_config('recipes_py')
    self.m.gclient.checkout()
    self.m.gclient.runhooks()

  def roll_projects(self, projects):
    """Attempts to roll each project from the provided list.

    If rolling any of the projects leads to failures, other
    projects are not affected.
    """
    project_data = self.m.luci_config.get_projects()
    with recipe_api.defer_results():
      for project in projects:
        with self.m.step.nest(str(project)):
          self._roll_project(project_data[project])

  def _roll_project(self, project_data):
    with self.m.tempfile.temp_dir('roll_%s' % project_data['id']) as workdir:
      self.m.git.checkout(
          project_data['repo_url'], dir_path=workdir, submodules=False)

      recipes_cfg_path = workdir.join('infra', 'config', 'recipes.cfg')

      roll_step = self.m.python('roll',
          self.m.path['checkout'].join('recipes-py', 'recipes.py'),
          ['--package', recipes_cfg_path, 'autoroll',
           '--output-json', self.m.json.output()])
      roll_result = roll_step.json.output

      if roll_result['success']:
        blame = []
        for project, commits in roll_result[
            'picked_roll_details']['commit_infos'].iteritems():
          blame.append('%s:' % project)
          for commit in commits:
            message = commit['message'].splitlines()
            # TODO(phajdan): truncate long messages.
            message = message[0] if message else 'n/a'
            # TODO(phajdan): get clickable links for the commits.
            blame.append('  %s %s (%s)' % (
                commit['revision'], message, commit['author']))
        roll_step.presentation.logs['blame'] = blame

        if roll_result['trivial']:
          roll_step.presentation.step_text += ' (trivial)'
        else:
          roll_step.presentation.status = self.m.step.WARNING
      else:
        if (not roll_result['roll_details'] and
            not roll_result['rejected_candidates_details']):
          roll_step.presentation.step_text += ' (already at latest revisions)'
        else:
          roll_step.presentation.status = self.m.step.FAILURE

      # TODO(phajdan): upload the CL.
      self.m.git('diff', 'HEAD', cwd=workdir)
