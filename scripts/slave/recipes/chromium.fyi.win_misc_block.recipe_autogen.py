# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'chromium',
    'depot_tools/bot_update',
    'depot_tools/gclient',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
]


def Chromium_Win_x64_Clobber_steps(api):
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
    soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
                        'googlecode_url': 'http://%s.googlecode.com/svn',
                        'nacl_trunk':
                        'http://src.chromium.org/native_client/trunk',
                        'sourceforge_url':
                        'https://svn.code.sf.net/p/%(repo)s/code',
                        'llvm_url': 'http://llvm.org/svn/llvm-project'}
    src_cfg.got_revision_mapping.update(
        {'src': 'got_revision',
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
           'GYP_GENERATORS': 'ninja',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': 'target_arch=x64 component=static_library',
           'LANDMINES_VERBOSE': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'out.sln', '--target', 'Release_x64', '--clobber',
            '--build-tool=ninja', '--', 'chromium_builder_tests']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    with api.step.defer_results():
      # runtest step
      api.python(
          "interactive_ui_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'interactive_ui_tests',
           'interactive_ui_tests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "base_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'base_unittests',
           'base_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "cacheinvalidation_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'cacheinvalidation_unittests',
           'cacheinvalidation_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "cc_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'cc_unittests',
           'cc_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "chromedriver_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'chromedriver_unittests',
           'chromedriver_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "components_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'components_unittests',
           'components_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "courgette_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'courgette_unittests',
           'courgette_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "crypto_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'crypto_unittests',
           'crypto_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "gcm_unit_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'gcm_unit_tests',
           'gcm_unit_tests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "gpu_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'gpu_unittests',
           'gpu_unittests.exe', '--gmock_verbose=error', '--gtest_print_time'])
      # runtest step
      api.python(
          "url_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'url_unittests',
           'url_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "jingle_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'jingle_unittests',
           'jingle_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "media_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'media_unittests',
           'media_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "net_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'net_unittests',
           'net_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "ppapi_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'ppapi_unittests',
           'ppapi_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "printing_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'printing_unittests',
           'printing_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "remoting_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'remoting_unittests',
           'remoting_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "sbox_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sbox_unittests',
           'sbox_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "sbox_integration_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sbox_integration_tests',
           'sbox_integration_tests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "sbox_validation_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sbox_validation_tests',
           'sbox_validation_tests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "ipc_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'ipc_tests', 'ipc_tests.exe',
           '--gtest_print_time'])
      # runtest step
      api.python(
          "sync_unit_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sync_unit_tests',
           'sync_unit_tests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "unit_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'unit_tests', 'unit_tests.exe',
           '--gtest_print_time'])
      # runtest step
      api.python(
          "skia_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'skia_unittests',
           'skia_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "sql_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sql_unittests',
           'sql_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "ui_base_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'ui_base_unittests',
           'ui_base_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "content_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'content_unittests',
           'content_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "views_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'views_unittests',
           'views_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "browser_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'browser_tests',
           'browser_tests.exe', '--lib=browser_tests', '--gtest_print_time'])
      # runtest step
      api.python(
          "content_browsertests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'content_browsertests',
           'content_browsertests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "installer_util_unittests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'installer_util_unittests',
           'installer_util_unittests.exe', '--gtest_print_time'])
      # runtest step
      api.python(
          "sync_integration_tests",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--target', 'Release_x64', "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           ('--factory-properties={"blink_config":"chromium","gclient_env":'
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
             '"GYP_DEFINES":"target_arch=x64 component=static_library",'
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"}}'),
           '--annotate=gtest', '--test-type', 'sync_integration_tests',
           'sync_integration_tests.exe', '--ui-test-action-max-timeout=120000',
           '--gtest_print_time'])
      # nacl_integration step
      api.python("nacl_integration",
                 api.path["subordinate_build"].join('src', 'chrome', 'test',
                                              'nacl_test_injection',
                                              'buildbot_nacl_integration.py'),
                 args=['--mode', 'Release_x64'],
                 env={},
                 cwd=api.path["subordinate_build"])


def Windows_8_App_Certification_steps(api):
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
    soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
                        'googlecode_url': 'http://%s.googlecode.com/svn',
                        'nacl_trunk':
                        'http://src.chromium.org/native_client/trunk',
                        'sourceforge_url':
                        'https://svn.code.sf.net/p/%(repo)s/code',
                        'llvm_url': 'http://llvm.org/svn/llvm-project'}
    src_cfg.got_revision_mapping.update(
        {'src': 'got_revision',
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
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'chrome.sln', '--target', 'Release']
    if "clobber" in api.properties:
        args.append("--clobber")
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)


dispatch_directory = {
    'Chromium Win x64 Clobber': Chromium_Win_x64_Clobber_steps,
    'Windows 8 App Certification': Windows_8_App_Certification_steps,
}


def RunSteps(api):
    if api.properties["buildername"] not in dispatch_directory:
        raise api.step.StepFailure("Builder unsupported by recipe.")
    else:
        dispatch_directory[api.properties["buildername"]](api)


def GenTests(api):
  yield (api.test('Chromium_Win_x64_Clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Chromium Win x64 Clobber') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_8_App_Certification') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows 8 App Certification') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_8_App_Certification_clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows 8 App Certification') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(clobber='') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
