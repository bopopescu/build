#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import json

BUILD_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
BUILD_INTERNAL_ROOT = os.path.join(
    os.path.dirname(BUILD_ROOT), 'build_internal')

sys.path.append(os.path.join(BUILD_ROOT, 'third_party'))

from recipe_engine import loader


def main(argv):
  roots = [BUILD_ROOT, BUILD_INTERNAL_ROOT]
  universe = loader.RecipeUniverse(
      module_dirs=[os.path.join(root, 'scripts', 'subordinate', 'recipe_modules')
                    for root in roots],
      recipe_dirs=[os.path.join(root, 'scripts', 'subordinate', 'recipes')
                    for root in roots])
  recipes = list(universe.loop_over_recipes())
  paths = []
  for _, name in recipes:
    recipe = universe.load_recipe(name)

    recipe_file = os.path.relpath(recipe.__file__)
    paths.append(recipe_file)

    # Strip off the .py
    expected_dir = recipe_file[:-3] + '.expected/'
    if os.path.exists(expected_dir):
      paths.append(expected_dir)

  cmd = [sys.executable, '../unittests/recipe_simulation_test.py'] + argv[1:]
  out = {
    'includes': [
        'recipes_test.isolate',
    ],
    'variables': {
      'command': cmd,
    },
  }

  out['variables']['files'] = paths
  print json.dumps(out, indent=2, sort_keys=True)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
