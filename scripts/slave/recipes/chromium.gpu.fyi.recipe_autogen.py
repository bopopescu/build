# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

def Win7_Audio_steps(api):
  build_properties = api.properties.legacy()
  # svnkill step; not necessary in recipes
  # update scripts step; implicitly run by recipe engine.
  # taskkill step
  api.python("taskkill", api.path["build"].join("scripts", "subordinate",
    "kill_processes.py"))
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/data/selenium_core': None,
      'src/data/page_cycler': None,
      'src/data/esctf': None,
      'src/data/mach_ports': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/data/autodiscovery': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/memory_test': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None}
  soln.custom_vars = {}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # gclient revert step; made unnecessary by bot_update
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1', 'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0',
      'GYP_DEFINES': 'fastbuild=1 component=static_library'}
  api.python("gclient runhooks wrapper",
      api.path["build"].join("scripts", "subordinate", "runhooks_wrapper.py"),
      env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # compile.py step
  args = ['--solution', 'all.sln', '--project', 'chromium_builder_tests',
      '--target', 'Release']
  # buildbot sets 'clobber' to the empty string which is falsey, check with 'in'
  if 'clobber' in api.properties:
    args.append("--clobber")
  api.step("compile", ["python_subordinate",
    api.path["build"].join("scripts", "subordinate", "compile.py")] + args)
  # runtest step
  api.step("content_unittests",
      ["python_subordinate", api.path["build"].join("scripts", "subordinate", "runtest.py"),
       '--target', 'Release',
       "--build-properties=%s" % api.json.dumps(build_properties,
         separators=(',', ':')),
       '--factory-properties={"blink_config":"chromium","gclient_env":{"CHROM'+\
       'IUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":"fas'+\
       'tbuild=1 component=static_library","LANDMINES_VERBOSE":"1"},"generate'+\
       '_gtest_json":true,"test_results_server":"test-results.appspot.com"}',
       '--annotate=gtest', '--test-type', 'content_unittests',
       '--generate-json-file', '-o', 'gtest-results/content_unittests',
       '--build-number', api.properties["buildnumber"], '--builder-name',
       api.properties["buildername"], 'content_unittests.exe',
       '--gtest_print_time'])
  # runtest step
  api.step("media_unittests",
      ["python_subordinate", api.path["build"].join("scripts", "subordinate", "runtest.py"),
       '--target', 'Release',
       "--build-properties=%s" % api.json.dumps(build_properties,
         separators=(',', ':')),
       '--factory-properties={"blink_config":"chromium","gclient_env":{"CHROM'+\
       'IUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":"fas'+\
       'tbuild=1 component=static_library","LANDMINES_VERBOSE":"1"},"generate'+\
       '_gtest_json":true,"test_results_server":"test-results.appspot.com"}',
       '--annotate=gtest', '--test-type', 'media_unittests',
       '--generate-json-file', '-o', 'gtest-results/media_unittests',
       '--build-number', api.properties["buildnumber"], '--builder-name',
       api.properties["buildername"], 'media_unittests.exe',
       '--gtest_print_time'])


def Linux_Audio_steps(api):
  build_properties = api.properties.legacy()
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/data/selenium_core': None,
      'src/data/page_cycler': None,
      'src/data/esctf': None,
      'src/data/mach_ports': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/data/autodiscovery': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/memory_test': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None}
  soln.custom_vars = {}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties.update(result.json.output.get("properties", {}))
  # gclient revert step; made unnecessary by bot_update
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1',
      'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0',
      'GYP_DEFINES': ' component=static_library'}
  api.python("gclient runhooks wrapper",
      api.path["build"].join("scripts", "subordinate", "runhooks_wrapper.py"),
      env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # compile.py step
  args = ['--target', 'Release', 'content_unittests', 'media_unittests']

  # buildbot sets 'clobber' to the empty string which is falsey, check with 'in'
  if 'clobber' in api.properties:
    args.append("--clobber")
  api.python("compile",
      api.path["build"].join("scripts", "subordinate", "compile.py"), args=args)
  # runtest step
  api.python("content_unittests",
      api.path["build"].join("scripts", "subordinate","runtest.py"),
      args=['--target', 'Release',
        "--build-properties=%s" % api.json.dumps(build_properties,
          separators=(',', ':')),
        '--factory-properties={"blink_config":"chromium","gclient_env":{"CHRO'+\
        'MIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":" '+\
        'component=static_library","LANDMINES_VERBOSE":"1"},"generate_gtest_j'+\
        'son":true,"test_results_server":"test-results.appspot.com"}',
        '--annotate=gtest', '--test-type', 'content_unittests',
        '--generate-json-file', '-o', 'gtest-results/content_unittests',
        '--build-number', api.properties["buildnumber"], '--builder-name',
        api.properties["buildername"], 'content_unittests',
        '--gtest_print_time'])
  # runtest step
  api.python("media_unittests",
      api.path["build"].join("scripts", "subordinate","runtest.py"),
      args=['--target', 'Release',
        "--build-properties=%s" % api.json.dumps(build_properties,
          separators=(',', ':')),
        '--factory-properties={"blink_config":"chromium","gclient_env":{"CHRO'+\
        'MIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":" '+\
        'component=static_library","LANDMINES_VERBOSE":"1"},"generate_gtest_j'+\
        'son":true,"test_results_server":"test-results.appspot.com"}',
        '--annotate=gtest', '--test-type', 'media_unittests',
        '--generate-json-file', '-o', 'gtest-results/media_unittests',
        '--build-number', api.properties["buildnumber"], '--builder-name',
        api.properties["buildername"], 'media_unittests', '--gtest_print_time'])


dispatch_directory = {
  'Win7 Audio': Win7_Audio_steps,
  'Linux Audio': Linux_Audio_steps,
}


def RunSteps(api):
  if api.properties["buildername"] not in dispatch_directory:
    raise api.step.StepFailure("Builder unsupported by recipe.")
  else:
    dispatch_directory[api.properties["buildername"]](api)

def GenTests(api):
  yield (api.test('Win7_Audio') +
    api.properties(mainname='chromium.gpu.fyi') +
    api.properties(buildername='Win7 Audio') +
    api.properties(subordinatename='TestSubordinate') +
    api.properties(buildnumber=42)
        )
  yield (api.test('Win7_Audio_clobber') +
    api.properties(mainname='chromium.gpu.fyi') +
    api.properties(buildername='Win7 Audio') +
    api.properties(subordinatename='TestSubordinate') +
    api.properties(buildnumber=42) +
    api.properties(clobber=True)
        )
  yield (api.test('Linux_Audio') +
    api.properties(mainname='chromium.gpu.fyi') +
    api.properties(buildername='Linux Audio') +
    api.properties(subordinatename='TestSubordinate') +
    api.properties(buildnumber=42)
        )
  yield (api.test('Linux_Audio_clobber') +
    api.properties(mainname='chromium.gpu.fyi') +
    api.properties(buildername='Linux Audio') +
    api.properties(subordinatename='TestSubordinate') +
    api.properties(buildnumber=42) +
    api.properties(clobber=True)
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.gpu.fyi') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
