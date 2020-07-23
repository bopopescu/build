#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import os
import subprocess
import sys
import tempfile


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


MAIN_WATERFALL_MASTERS = [
    'main.chromium',
    'main.chromium.chrome',
    'main.chromium.chromiumos',
    'main.chromium.gpu',
    'main.chromium.linux',
    'main.chromium.mac',
    'main.chromium.memory',
    'main.chromium.win',
]


TRYSERVER_MASTERS = [
    'main.tryserver.chromium.android',
    'main.tryserver.chromium.linux',
    'main.tryserver.chromium.mac',
    'main.tryserver.chromium.win',
]


SUPPRESSIONS = {
    'main.chromium.chrome': [
        'Google Chrome ChromeOS',
        'Google Chrome Linux x64',
        'Google Chrome Mac',
        'Google Chrome Win',
    ],
    'main.chromium.chromiumos': [
        'Linux ChromiumOS Full',
    ],
    'main.chromium.gpu': [
        'Android Debug (Nexus 5)',
        'Android Debug (Nexus 6)',
        'Android Debug (Nexus 9)',
        'GPU Linux Builder (dbg)',
        'GPU Mac Builder (dbg)',
        'GPU Win Builder (dbg)',
        'Linux Debug (NVIDIA)',
        'Mac 10.10 Debug (Intel)',
        'Mac Retina Debug',
        'Mac 10.10 Retina Debug (AMD)',
        'Mac 10.10 Retina Release (AMD)',
        'Win7 Debug (NVIDIA)',
    ],
    'main.chromium.mac': [
        'Mac10.11 Tests',
        'iOS_Device',
        'iOS_Device_GN',
        'iOS_Device_(ninja)',
        'iOS_Simulator_GN_(dbg)',
        'iOS_Simulator_(dbg)',
    ],
    'main.chromium.memory': [
        'Linux ASan Tests (sandboxed)',
    ],
    'main.chromium.win': [
        'Win7 (32) Tests',
        'Win x64 Builder (dbg)',
    ],
}


def getBuilders(recipe_name, deps_path):
  """Asks the given recipe to dump its BUILDERS dictionary.

  This must be implemented by the recipe in question.

  deps_path is where the recipe engine should download the dependent recipe
  packages. This is to avoid git.lock collision.
  """
  (fh, builders_file) = tempfile.mkstemp('.json')
  os.close(fh)
  try:
    subprocess.check_call([
        os.path.join(BASE_DIR, 'scripts', 'subordinate', 'recipes.py'),
        '--deps-path', deps_path,
        'run', recipe_name, 'dump_builders=%s' % builders_file])
    with open(builders_file) as fh:
      return json.load(fh)
  finally:
    os.remove(builders_file)


def getCQBuilders(cq_config):
  # This relies on 'commit_queue' tool from depot_tools.
  output = subprocess.check_output(['commit_queue', 'builders', cq_config])
  return json.loads(output)


def getMainConfig(main):
  with tempfile.NamedTemporaryFile() as f:
    subprocess.check_call([
        os.path.join(BASE_DIR, 'scripts', 'tools', 'runit.py'),
        os.path.join(BASE_DIR, 'scripts', 'tools', 'dump_main_cfg.py'),
        os.path.join(BASE_DIR, 'mains/%s' % main),
        f.name])
    return json.load(f)


def getBuildersAndRecipes(main):
  return {
      builder['name'] : builder['factory']['properties'].get(
          'recipe', [None])[0]
      for builder in getMainConfig(main)['builders']
  }


def mutualDifference(a, b):
  return a - b, b - a


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('--cq-config', help='Path to CQ config')
  parser.add_argument('--verbose', action='store_true')
  args = parser.parse_args()

  chromium_recipe_builders = {}
  covered_builders = set()
  all_builders = set()

  exit_code = 0

  current_dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
  chromium_trybot_BUILDERS = getBuilders(
      'chromium_trybot', os.path.join(
          current_dir, '.chromium_trybot_recipe_deps'))
  chromium_BUILDERS = getBuilders(
      'chromium', os.path.join(
          current_dir, '.chromium_recipe_deps'))

  cq_builders = getCQBuilders(args.cq_config) if args.cq_config else None

  for main in MAIN_WATERFALL_MASTERS:
    builders = getBuildersAndRecipes(main)
    all_builders.update((main, b) for b in builders)

    # We only have a standardized way to mirror builders using the chromium
    # recipe on the tryserver.
    chromium_recipe_builders[main] = [b for b in builders
                                        if builders[b] == 'chromium']

    recipe_side_builders = chromium_BUILDERS.get(
        main.replace('main.', ''), {}).get('builders')
    if recipe_side_builders is not None:
      bogus_builders = set(recipe_side_builders.keys()).difference(
          set(builders.keys()))
      if bogus_builders:
        exit_code = 1
        print 'The following builders from chromium recipe'
        print 'do not exist in main config for %s:' % main
        print '\n'.join('\t%s' % b for b in sorted(bogus_builders))

      other_recipe_builders = set(recipe_side_builders.keys()).difference(
          set(chromium_recipe_builders[main]))
      if other_recipe_builders:
        exit_code = 1
        print 'The following builders from chromium recipe'
        print 'are configured to run a different recipe on the main'
        print '(%s):' % main
        print '\n'.join('\t%s' % b for b in sorted(other_recipe_builders))


  for main in TRYSERVER_MASTERS:
    short_main = main.replace('main.', '')
    builders = getBuildersAndRecipes(main)
    recipe_side_builders = chromium_trybot_BUILDERS[
        short_main]['builders']

    bogus_builders = set(recipe_side_builders.keys()).difference(
        set(builders.keys()))
    if bogus_builders:
      exit_code = 1
      print 'The following builders from chromium_trybot recipe'
      print 'do not exist in main config for %s:' % main
      print '\n'.join('\t%s' % b for b in sorted(bogus_builders))

    for builder, recipe in builders.iteritems():
      # Only the chromium_trybot recipe knows how to mirror a main waterfall
      # builder.
      if recipe != 'chromium_trybot':
        continue

      bot_config = recipe_side_builders.get(builder)
      if not bot_config:
        continue

      if args.cq_config and builder not in cq_builders.get(short_main, {}):
        continue

      # TODO(phajdan.jr): Make it an error if any builders referenced here
      # are not using chromium recipe.
      for bot_id in bot_config['bot_ids']:
        main_waterfall_main = 'main.' + bot_id['mainname']
        bots = [bot_id['buildername']]
        if bot_id.get('tester'):
          bots.append(bot_id['tester'])
        for mw_builder in bots:
          if mw_builder in chromium_recipe_builders.get(
              main_waterfall_main, []):
            covered_builders.add((main_waterfall_main, mw_builder))

  # TODO(phajdan.jr): Add a way to only count trybots launched by CQ by default.
  print 'Main waterfall ng-trybot coverage: %.2f' % (
      100.0 * len(covered_builders) / len(all_builders))

  not_covered_builders = all_builders.difference(covered_builders)
  suppressed_builders = set()
  for main, builders in SUPPRESSIONS.iteritems():
    suppressed_builders.update((main, b) for b in builders)

  regressed_builders = not_covered_builders.difference(suppressed_builders)
  if regressed_builders:
    exit_code = 1
    print 'Regression, the following builders lack in-sync tryserver coverage:'
    print '\n'.join(sorted(
        '\t%s:%s' % (b[0], b[1]) for b in regressed_builders))

  unused_suppressions = suppressed_builders.difference(not_covered_builders)
  if unused_suppressions:
    exit_code = 1
    print 'Unused suppressions:'
    print '\n'.join(sorted(
        '\t%s:%s' % (b[0], b[1]) for b in unused_suppressions))

  return exit_code


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
