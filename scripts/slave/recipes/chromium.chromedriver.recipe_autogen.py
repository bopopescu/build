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

def Linux32_steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/chrome/test/chromedriver/third_party/java_tests':
      'https://chromium.googlesource.com/chromium/deps/webdriver'}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/webkit/data/test_shell/plugins': None,
      'src/data/page_cycler': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/esctf': None,
      'src/data/memory_test': None,
      'src/data/mach_ports': None,
      'src/webkit/data/xbm_decoder': None,
      'src/webkit/data/ico_decoder': None,
      'src/data/selenium_core': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/webkit/data/bmp_decoder': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None,
      'src/data/autodiscovery': None}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties = api.properties.legacy()
  build_properties.update(result.json.output.get('properties', {}))
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1', 'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0',
      'GYP_DEFINES':
      'branding=Chrome buildtype=Official component=static_library'}
  api.python("gclient runhooks wrapper", api.path["build"].join("scripts",
    "subordinate", "runhooks_wrapper.py"), env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # chromedriver compile.py step
  api.python("compile", api.path["build"].join("scripts", "subordinate",
    "compile.py"), args=['--target', 'Release',
      'chromium_builder_chromedriver'])
  # annotated_steps step
  api.python("annotated_steps", api.path["build"].join("scripts", "subordinate",
    "chromium", "chromedriver_buildbot_run.py"),
    args=['--build-properties=%s' % api.json.dumps(build_properties,
      separators=(',', ':')), '--factory-properties={"annotated_script":'+\
          '"chromedriver_buildbot_run.py","blink_config":"chromium",'+\
          '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
          '"DEPOT_TOOLS_UPDATE"'':"0","GYP_DEFINES":"branding=Chrome '+\
          'buildtype=Official component=static_library","LANDMINES_VERBOSE":'+\
          '"1"},"needs_webdriver_java_tests":true,"use_xvfb_on_linux":true}'],
    allow_subannotations=True)


def Mac_10_6_steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/chrome/test/chromedriver/third_party/java_tests':
      'https://chromium.googlesource.com/chromium/deps/webdriver'}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/webkit/data/test_shell/plugins': None,
      'src/data/page_cycler': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/esctf': None,
      'src/data/memory_test': None,
      'src/data/mach_ports': None,
      'src/webkit/data/xbm_decoder': None,
      'src/webkit/data/ico_decoder': None,
      'src/data/selenium_core': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/webkit/data/bmp_decoder': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None,
      'src/data/autodiscovery': None}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties = api.properties.legacy()
  build_properties.update(result.json.output.get('properties', {}))
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1', 'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0', 'GYP_DEFINES': ' component=static_library'}
  api.python("gclient runhooks wrapper", api.path["build"].join("scripts",
    "subordinate", "runhooks_wrapper.py"), env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # chromedriver compile.py step
  api.python("compile", api.path["build"].join("scripts", "subordinate",
    "compile.py"), args=['--target', 'Release', '--', '-project',
      '../build/all.xcodeproj', '-target', 'chromium_builder_chromedriver'])
  # annotated_steps step
  api.python("annotated_steps", api.path["build"].join("scripts", "subordinate",
    "chromium", "chromedriver_buildbot_run.py"),
    args=['--build-properties=%s' % api.json.dumps(build_properties,
      separators=(',', ':')), '--factory-properties={"annotated_script":"c'+\
          'hromedriver_buildbot_run.py","blink_config":"chromium","gclient_e'+\
          'nv":{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP'+\
          '_DEFINES":" component=static_library","LANDMINES_VERBOSE":"1"},"ne'+\
          'eds_webdriver_java_tests":true}'], allow_subannotations=True)


def Win7_steps(api):
  # update scripts step; implicitly run by recipe engine.
  # taskkill step
  api.python("taskkill", api.path["build"].join("scripts", "subordinate",
    "kill_processes.py"))
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/chrome/test/chromedriver/third_party/java_tests':
      'https://chromium.googlesource.com/chromium/deps/webdriver'}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/webkit/data/test_shell/plugins': None,
      'src/data/page_cycler': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/esctf': None,
      'src/data/memory_test': None,
      'src/data/mach_ports': None,
      'src/webkit/data/xbm_decoder': None,
      'src/webkit/data/ico_decoder': None,
      'src/data/selenium_core': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/webkit/data/bmp_decoder': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None,
      'src/data/autodiscovery': None}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties = api.properties.legacy()
  build_properties.update(result.json.output.get('properties', {}))
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1', 'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0','GYP_DEFINES': ' component=static_library'}
  api.python("gclient runhooks wrapper", api.path["build"].join("scripts",
    "subordinate", "runhooks_wrapper.py"), env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # chromedriver compile.py step
  api.step("compile", ["python_subordinate", api.path["build"].join("scripts",
    "subordinate", "compile.py"), '--solution', 'all.sln', '--project',
    'chromium_builder_chromedriver', '--target', 'Release'])
  # annotated_steps step
  api.step("annotated_steps", ["python_subordinate", api.path["build"].join("scripts",
    "subordinate", "chromium", "chromedriver_buildbot_run.py"),
    '--build-properties=%s' % api.json.dumps(build_properties,
      separators=(',', ':')), '--factory-properties={"annotated_script":"chro'+\
          'medriver_buildbot_run.py","blink_config":"chromium","gclient_env":'+\
          '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEF'+\
          'INES":" component=static_library","LANDMINES_VERBOSE":"1"},"needs_'+\
          'webdriver_java_tests":true}'], allow_subannotations=True)


def Linux_steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/chrome/test/chromedriver/third_party/java_tests':
      'https://chromium.googlesource.com/chromium/deps/webdriver'}
  soln = src_cfg.solutions.add()
  soln.name = "src-internal"
  soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
  soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
      'src/tools/grit/grit/test/data': None,
      'src/chrome/test/data/firefox3_searchplugins': None,
      'src/webkit/data/test_shell/plugins': None,
      'src/data/page_cycler': None,
      'src/data/mozilla_js_tests': None,
      'src/chrome/test/data/firefox2_profile/searchplugins': None,
      'src/data/esctf': None,
      'src/data/memory_test': None,
      'src/data/mach_ports': None,
      'src/webkit/data/xbm_decoder': None,
      'src/webkit/data/ico_decoder': None,
      'src/data/selenium_core': None,
      'src/chrome/test/data/ssl/certs': None,
      'src/chrome/test/data/osdd': None,
      'src/webkit/data/bmp_decoder': None,
      'src/chrome/test/data/firefox3_profile/searchplugins': None,
      'src/data/autodiscovery': None}
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  result = api.bot_update.ensure_checkout(force=True)
  build_properties = api.properties.legacy()
  build_properties.update(result.json.output.get('properties', {}))
  # gclient update step; made unnecessary by bot_update
  # gclient runhooks wrapper step
  env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1', 'LANDMINES_VERBOSE': '1',
      'DEPOT_TOOLS_UPDATE': '0', 'GYP_DEFINES':
      'branding=Chrome buildtype=Official component=static_library'}
  api.python("gclient runhooks wrapper", api.path["build"].join("scripts",
    "subordinate", "runhooks_wrapper.py"), env=env)
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # chromedriver compile.py step
  api.python("compile", api.path["build"].join("scripts", "subordinate",
    "compile.py"), args=['--target', 'Release',
      'chromium_builder_chromedriver'])
  # annotated_steps step
  api.python("annotated_steps", api.path["build"].join("scripts", "subordinate",
    "chromium", "chromedriver_buildbot_run.py"),
    args=['--build-properties=%s' % api.json.dumps(build_properties,
      separators=(',', ':')), '--factory-properties={"annotated_script":"chro'+\
          'medriver_buildbot_run.py","blink_config":"chromium","gclient_env":'+\
          '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0","GYP_DEF'+\
          'INES":"branding=Chrome buildtype=Official component=static_library'+\
          '","LANDMINES_VERBOSE":"1"},"needs_webdriver_java_tests":true,"use_'+\
          'xvfb_on_linux":true}'], allow_subannotations=True)


dispatch_directory = {
  'Linux32': Linux32_steps,
  'Mac 10.6': Mac_10_6_steps,
  'Win7': Win7_steps,
  'Linux': Linux_steps,
}


def RunSteps(api):
  if api.properties["buildername"] not in dispatch_directory:
    raise api.step.StepFailure("Builder unsupported by recipe.")
  else:
    dispatch_directory[api.properties["buildername"]](api)

def GenTests(api):
  yield (api.test('Linux32') +
    api.properties(mainname='chromium.chromedriver') +
    api.properties(buildername='Linux32') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Mac_10_6') +
    api.properties(mainname='chromium.chromedriver') +
    api.properties(buildername='Mac 10.6') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Win7') +
    api.properties(mainname='chromium.chromedriver') +
    api.properties(buildername='Win7') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Linux') +
    api.properties(mainname='chromium.chromedriver') +
    api.properties(buildername='Linux') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.chromedriver') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
