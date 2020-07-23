# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'gsutil',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',
]

def win_xp_dr_nightly_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # dynamorio win nightly suite step
  api.step("nightly suite",
      [api.path["build"].join("scripts", "subordinate", "drmemory", "build_env.bat"),
        'ctest', '--timeout', '120', '-VV', '-S',
        'dynamorio/suite/runsuite.cmake,nightly;long;'+\
            'site=X64.WindowsXp.VS2010.BuildBot'],
      env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
        "bot_tools")}, cwd=api.path["subordinate_build"])


def linux_dr_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # pre-commit suite step
  api.step("pre-commit suite", ['ctest', '--timeout', '120', '-VV', '-S',
    api.path["checkout"].join("suite", "runsuite.cmake")],
    cwd=api.path["subordinate_build"], ok_ret="all")
  # upload dynamorio docs step
  api.gsutil.upload(api.path["subordinate_build"].join("install", "docs", "html"),
      "chromium-dynamorio", "dr_docs/", ["-r"], multithreaded=True)


def win_7_dr_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # build_env step
  api.step("pre-commit suite", [api.path["build"].join("scripts", "subordinate",
    "drmemory", "build_env.bat"), 'ctest', '--timeout', '120', '-VV', '-S',
    api.path["checkout"].join("suite", "runsuite.cmake")],
    env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
      "bot_tools")}, cwd=api.path["subordinate_build"])


def linux_dr_package_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # get buildnumber step; no longer needed
  # Package DynamoRIO step
  api.step("Package DynamoRIO", ["ctest", "-VV", "-S",
    str(api.path["checkout"].join("make", "package.cmake")) + ",build=0x" +
    build_properties["got_revision"][:7]])
  # find package file step; no longer necessary
  # upload dynamorio package
  api.gsutil.upload("DynamoRIO-Linux-*" +
      build_properties["got_revision"][:7] +
      ".tar.gz", "chromium-dynamorio", "builds/")


def win_8_dr_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # build_env step
  api.step("pre-commit suite",
      [api.path["build"].join("scripts", "subordinate", "drmemory", "build_env.bat"),
        'ctest', '--timeout', '120', '-VV', '-S',
        api.path["checkout"].join("suite", "runsuite.cmake")],
      env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
        "bot_tools")}, cwd=api.path["subordinate_build"])


def win_xp_dr_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # build_env step
  api.step("pre-commit suite", [api.path["build"].join("scripts", "subordinate",
    "drmemory", "build_env.bat"), 'ctest', '--timeout', '120', '-VV', '-S',
    api.path["checkout"].join("suite", "runsuite.cmake")],
    env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
      "bot_tools")}, cwd=api.path["subordinate_build"])


def win_7_dr_nightly_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # dynamorio win nightly suite step
  api.step("nightly suite", [api.path["build"].join("scripts", "subordinate",
    "drmemory", "build_env.bat"), 'ctest', '--timeout', '120', '-VV', '-S',
    'dynamorio/suite/runsuite.cmake,nightly;long;'+\
        'site=X64.Windows7.VS2010.BuildBot'],
    env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
      "bot_tools")}, cwd=api.path["subordinate_build"])


def win_8_dr_nightly_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # dynamorio win nightly suite step
  api.step("nightly suite", [api.path["build"].join("scripts", "subordinate",
    "drmemory", "build_env.bat"), 'ctest', '--timeout', '120', '-VV', '-S',
    'dynamorio/suite/runsuite.cmake,nightly;long;'+\
        'site=X64.Windows8.VS2010.BuildBot'],
    env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
      "bot_tools")}, cwd=api.path["subordinate_build"])


def win_dr_package_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  soln.custom_deps = {'dynamorio/tools/buildbot':
      'https://github.com/DynamoRIO/buildbot.git'}
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # unpack tools step; generic ShellCommand converted
  api.step("unpack tools", [api.path["checkout"].join('tools', 'buildbot',
    'bot_tools', 'unpack.bat')], env={},
      cwd=api.path["checkout"].join('tools', 'buildbot', 'bot_tools'))
  # get buildnumber step; no longer needed
  # Package DynamoRIO step
  api.step("Package DynamoRIO", [api.path["build"].join("scripts", "subordinate",
    "drmemory", "build_env.bat"), "ctest", "-VV", "-S",
    str(api.path["checkout"].join("make", "package.cmake")) + ",build=0x" +
    build_properties["got_revision"][:7]],
    env={"BOTTOOLS": api.path["checkout"].join("tools", "buildbot",
      "bot_tools")})
  # find package file step; no longer necessary
  # upload dynamorio package
  api.gsutil.upload("DynamoRIO-Windows-*" +
      build_properties["got_revision"][:7]
      + ".zip", "chromium-dynamorio", "builds/")


def linux_dr_nightly_steps(api):
  build_properties = api.properties.legacy()
  # checkout DynamiRIO step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "dynamorio"
  soln.url = "https://github.com/DynamoRIO/dynamorio.git"
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # dynamorio nightly suite step
  api.step("nightly suite", ["ctest", "--timeout", "120", "-VV", "-S",
    str(api.path["checkout"].join("suite", "runsuite.cmake")) +
    ",nightly;long;site=X64.Linux.VS2010.BuildBot"])


dispatch_directory = {
  'win-xp-dr-nightly': win_xp_dr_nightly_steps,
  'linux-dr': linux_dr_steps,
  'win-7-dr': win_7_dr_steps,
  'linux-dr-package': linux_dr_package_steps,
  'win-8-dr': win_8_dr_steps,
  'win-xp-dr': win_xp_dr_steps,
  'win-7-dr-nightly': win_7_dr_nightly_steps,
  'win-8-dr-nightly': win_8_dr_nightly_steps,
  'win-dr-package': win_dr_package_steps,
  'linux-dr-nightly': linux_dr_nightly_steps,
}


def RunSteps(api):
  if api.properties["buildername"] not in dispatch_directory:
    raise api.step.StepFailure("Builder unsupported by recipe.")
  else:
    dispatch_directory[api.properties["buildername"]](api)

def GenTests(api):
  yield (api.test('win_xp_dr_nightly') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-xp-dr-nightly') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('linux_dr') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='linux-dr') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_7_dr') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-7-dr') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('linux_dr_package') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='linux-dr-package') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_8_dr') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-8-dr') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_xp_dr') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-xp-dr') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_7_dr_nightly') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-7-dr-nightly') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_8_dr_nightly') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-8-dr-nightly') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('win_dr_package') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='win-dr-package') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('linux_dr_nightly') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='linux-dr-nightly') +
    api.properties(revision='123456789abcdef') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='client.dynamorio') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
