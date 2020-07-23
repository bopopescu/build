# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class FinditApi(recipe_api.RecipeApi):

  def _calculate_repo_dir(self, solution_name):
    """Returns the relative path of the solution checkout to the root one."""
    if solution_name == 'src':
      return ''
    else:
      root_solution_name = 'src/'
      assert solution_name.startswith(root_solution_name)
      return solution_name[len(root_solution_name):]

  def files_changed_by_revision(self, revision, solution_name='src'):
    """Returns the files changed by the given revision.

    Args:
      revision (str): the git hash of a commit.
      solution_name (str): the gclient solution name, eg:
          "src" for chromium, "src/third_party/pdfium" for pdfium.
    """
    solution_name = solution_name.replace('\\', '/')
    repo_dir = self._calculate_repo_dir(solution_name)
    cwd = self.m.path['checkout'].join(repo_dir)

    previous_revision = '%s~1' % revision
    step_result = self.m.git('diff', revision + '~1', revision, '--name-only',
                             name='git diff to analyze commit',
                             stdout=self.m.raw_io.output(),
                             cwd=cwd,
                             step_test_data=lambda:
                                 self.m.raw_io.test_api.stream_output('foo.cc'))

    paths = step_result.stdout.split()
    if repo_dir:
      paths = [self.m.path.join(repo_dir, path) for path in paths]
    if self.m.platform.is_win:
      # Looks like "analyze" wants POSIX slashes even on Windows (since git
      # uses that format even on Windows).
      paths = [path.replace('\\', '/') for path in paths]

    step_result.presentation.logs['files'] = paths
    return paths

  def revisions_between(
      self, start_revision, end_revision, solution_name='src'):
    """Returns the git commit hashes between the given range.

    Args:
      start_revision (str): the git hash of a parent commit.
      end_revision (str): the git hash of a child commit.
      solution_name (str): the gclient solution name, eg:
          "src" for chromium, "src/third_party/pdfium" for pdfium.

    Returns:
      A list of git commit hashes between `start_revision` (excluded) and
      `end_revision` (included), ordered from older commits to newer commits.
    """
    solution_name = solution_name.replace('\\', '/')
    repo_dir = self._calculate_repo_dir(solution_name)
    cwd = self.m.path['checkout'].join(repo_dir)

    step_result = self.m.git('log', '--format=%H',
                             '%s..%s' % (start_revision, end_revision),
                             name='git commits in range',
                             stdout=self.m.raw_io.output(),
                             cwd=cwd,
                             step_test_data=lambda:
                                 self.m.raw_io.test_api.stream_output('r1'))

    revisions = step_result.stdout.split()
    revisions.reverse()

    step_result.presentation.logs['revisions'] = revisions
    return revisions

  def existing_targets(self, targets, mb_mainname, mb_buildername):
    """Returns a sublist of the given targets that exist in the build graph.

    We test whether a target exists or not by ninja.

    A "target" here is actually a node in ninja's build graph. For example:
      1. An executable target like browser_tests
      2. An object file like obj/path/to/Source.o
      3. An action like build/linux:gio_loader
      4. An generated header file like gen/library_loaders/libgio.h
      5. and so on

    Args:
     targets (list): A list of targets to be tested for existence.
     mb_mainname (str): The mainname to run MB with.
     mb_buildername (str): The buildername to run MB with.
    """
    # Run mb to generate or update ninja build files.
    if self.m.chromium.c.project_generator.tool == 'mb':
      self.m.chromium.run_mb(mb_mainname, mb_buildername,
                             name='generate_build_files')

    # Run ninja to check existences of targets.
    args = ['--target-build-dir', self.m.chromium.output_dir]
    for target in targets:
      args.extend(['--target', target])
    args.extend(['--json-output', self.m.json.output()])
    step = self.m.python(
        'check_targets', self.resource('check_target_existence.py'), args=args)
    return step.json.output['found']
