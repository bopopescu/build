#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides simulator test coverage for individual recipes."""

import logging
import os

# Importing for side effects on sys.path? Yes... yes we are :(
import test_env  # pylint: disable=W0611,W0403

from slave import recipe_util

import expect_tests  # pylint: disable=W0403


_UNIVERSE = None
def get_universe():
  from slave import recipe_loader
  global _UNIVERSE
  if _UNIVERSE is None:
    _UNIVERSE = recipe_loader.RecipeUniverse()
  return _UNIVERSE


def RunRecipe(test_data):
  from common import annotator
  from slave import annotated_run
  from slave import recipe_config_types

  stream = annotator.StructuredAnnotationStream(stream=open(os.devnull, 'w'))
  recipe_config_types.ResetTostringFns()
  # TODO(iannucci): Only pass test_data once.
  result = annotated_run.run_steps(stream, test_data.properties,
                                   test_data.properties,
                                   get_universe(),
                                   test_data)

  return expect_tests.Result(list(result.steps_ran.values()))


def test_gen_coverage():
  return (
      [os.path.join(x, '*') for x in recipe_util.RECIPE_DIRS()] +
      [os.path.join(x, '*', 'example.py') for x in recipe_util.MODULE_DIRS()] +
      [os.path.join(x, '*', 'test_api.py') for x in recipe_util.MODULE_DIRS()] +
      [os.path.join(os.path.dirname(recipe_util.__file__), 'recipe_api.py')]
  )


@expect_tests.covers(test_gen_coverage)
def GenerateTests():
  from slave import recipe_loader

  universe = get_universe()

  cover_mods = [
    os.path.join(os.path.dirname(recipe_util.__file__), 'recipe_api.py')
  ]
  for mod_dir_base in recipe_util.MODULE_DIRS():
    if os.path.isdir(mod_dir_base):
      cover_mods.append(os.path.join(mod_dir_base, '*', '*.py'))

  for recipe_path, recipe_name in recipe_loader.loop_over_recipes():
    recipe = universe.load_recipe(recipe_name)
    test_api = recipe_loader.create_test_api(recipe.LOADED_DEPS, universe)

    covers = cover_mods + [recipe_path]

    for test_data in recipe.GenTests(test_api):
      root, name = os.path.split(recipe_path)
      name = os.path.splitext(name)[0]
      expect_path = os.path.join(root, '%s.expected' % name)

      test_data.properties['recipe'] = recipe_name.replace('\\', '/')
      yield expect_tests.Test(
          '%s.%s' % (recipe_name, test_data.name),
          expect_tests.FuncCall(RunRecipe, test_data),
          expect_dir=expect_path,
          expect_base=test_data.name,
          covers=covers,
          break_funcs=(recipe.GenSteps,)
      )


if __name__ == '__main__':
  # annotated_run.py has different behavior when these environment variables
  # are set, so unset to make simulation tests environment-invariant.
  for env_var in ['TESTING_MASTER_HOST',
                  'TESTING_MASTER',
                  'TESTING_SLAVENAME']:
    if env_var in os.environ:
      logging.warn("Ignoring %s environment variable." % env_var)
      os.environ.pop(env_var)

  expect_tests.main('recipe_simulation_test', GenerateTests)
