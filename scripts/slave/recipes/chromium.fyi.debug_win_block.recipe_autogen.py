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
    'trigger',
]


def Vista_Tests__dbg__1__steps(api):
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
           'GYP_CHROMIUM_NO_ACTION': '1',
           'LANDMINES_VERBOSE': '1',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': ' component=shared_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # extract build step
    api.python(
        "extract build",
        api.path["build"].join("scripts", "subordinate", "extract_build.py"),
        args=["--target", "Debug", "--build-archive-url", build_properties[
            "parent_build_archive_url"], '--build-properties=%s' %
              api.json.dumps(build_properties,
                             separators=(',', ':'))])
    # start crash handler step
    api.python("start crash handler",
               api.path["build"].join("scripts", "subordinate", "chromium",
                                      "run_crash_handler.py"),
               args=["--target", "Debug"])
    # runtest step
    api.python(
        "base_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'base_unittests',
         'base_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "cacheinvalidation_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'cacheinvalidation_unittests',
         'cacheinvalidation_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "chrome_elf_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'chrome_elf_unittests',
         'chrome_elf_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "components_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'components_unittests',
         'components_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "courgette_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'courgette_unittests',
         'courgette_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "crypto_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'crypto_unittests',
         'crypto_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "extensions_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'extensions_unittests',
         'extensions_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "gcm_unit_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'gcm_unit_tests',
         'gcm_unit_tests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "google_apis_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'google_apis_unittests',
         'google_apis_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "gpu_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'gpu_unittests',
         'gpu_unittests.exe', '--gmock_verbose=error', '--gtest_print_time'])
    # runtest step
    api.python(
        "url_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'url_unittests',
         'url_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "jingle_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'jingle_unittests',
         'jingle_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "device_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'device_unittests',
         'device_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "media_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'media_unittests',
         'media_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "net_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'net_unittests',
         'net_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "ppapi_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'ppapi_unittests',
         'ppapi_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "printing_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'printing_unittests',
         'printing_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "remoting_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'remoting_unittests',
         'remoting_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "sbox_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'sbox_unittests',
         'sbox_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "sbox_integration_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'sbox_integration_tests',
         'sbox_integration_tests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "sbox_validation_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'sbox_validation_tests',
         'sbox_validation_tests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "ipc_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'ipc_tests', 'ipc_tests.exe',
         '--gtest_print_time'])
    # runtest step
    api.python(
        "sync_unit_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'sync_unit_tests',
         'sync_unit_tests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "unit_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'unit_tests', 'unit_tests.exe',
         '--gtest_print_time'])
    # runtest step
    api.python(
        "skia_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'skia_unittests',
         'skia_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "sql_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'sql_unittests',
         'sql_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "ui_base_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'ui_base_unittests',
         'ui_base_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "content_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'content_unittests',
         'content_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "views_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'views_unittests',
         'views_unittests.exe', '--gtest_print_time'])
    # runtest step
    api.python(
        "installer_util_unittests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":'+\
             '"1","GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'installer_util_unittests',
         'installer_util_unittests.exe', '--gtest_print_time'])
    # process dumps step
    api.python("process dumps",
               api.path["build"].join("scripts", "subordinate", "process_dumps.py"),
               args=["--target", "Debug"])


def Chromium_Builder__dbg__steps(api):
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
           'GYP_DEFINES': 'fastbuild=1 component=shared_library',
           'GYP_MSVS_VERSION': '2015'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'all.sln', '--project', 'chromium_builder_tests',
            '--target', 'Debug', '--compiler=goma']
    if "clobber" in api.properties:
        args.append("--clobber")
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # zip_build step
    step_result = api.python(
        "zip build",
        api.path["build"].join("scripts", "subordinate", "zip_build.py"),
        args=
        ["--json-urls", api.json.output(), "--target", "Debug", '--build-url',
         'gs://chromium-build-transfer/Chromium FYI Builder (dbg)',
         '--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":'+\
             '"fastbuild=1 component=shared_library",'+\
             '"GYP_MSVS_VERSION":"2015","LANDMINES_VERBOSE":"1"},'+\
             '"trigger":"win_dbg"}'
         ])
    if "storage_url" in step_result.json.output:
        step_result.presentation.links["download"] = step_result.json.output[
            "storage_url"]
    build_properties["build_archive_url"] = step_result.json.output["zip_url"]
    # trigger step
    trigger_spec = [
        {'builder_name': 'Vista Tests (dbg)(1)',
         "properties":
         {"parent_got_angle_revision":
          build_properties.get("got_angle_revision", ""),
          "parent_wk_revision":
          build_properties.get("got_webkit_revision", ""),
          "parent_got_v8_revision":
          build_properties.get("got_v8_revision", ""),
          "parent_got_swarming_client_revision":
          build_properties.get("got_swarming_client_revision", ""),
          "parent_build_archive_url":
          build_properties.get("build_archive_url", ""),
          "parent_revision": build_properties.get("revision", ""),
          "parent_subordinatename": build_properties.get("subordinatename", ""),
          "parent_scheduler": build_properties.get("scheduler", ""),
          "parentname": build_properties.get("builderna", ""),
          "parent_buildnumber": build_properties.get("buildnumber", ""),
          "patchset": build_properties.get("patchset", ""),
          "issue": build_properties.get("issue", ""),
          "parent_try_job_key": build_properties.get("try_job_key", ""),
          "parent_got_webkit_revision": build_properties.get(
              "got_webkit_revision", ""),
          "parent_builddir": build_properties.get("builddir", ""),
          "parent_branch": build_properties.get("branch", ""),
          "parent_got_clang_revision": build_properties.get(
              "got_clang_revision", ""),
          "requester": build_properties.get("requester", ""),
          "parent_cr_revision": build_properties.get("got_revision", ""),
          "rietveld": build_properties.get("rietveld", ""),
          "parent_got_nacl_revision": build_properties.get("got_nacl_revision",
                                                           ""),
          "parent_buildername": build_properties.get("buildername", ""),
          "parent_got_revision": build_properties.get("got_revision", ""),
          "patch_url": build_properties.get("patch_url", ""),
          "parent_git_number": build_properties.get("git_number", ""),
          "parentsubordinatename": build_properties.get("subordinatename", ""),
          "root": build_properties.get("root", ""), }},
        {'builder_name': 'Vista Tests (dbg)(2)',
         "properties":
         {"parent_got_angle_revision":
          build_properties.get("got_angle_revision", ""),
          "parent_wk_revision":
          build_properties.get("got_webkit_revision", ""),
          "parent_got_v8_revision":
          build_properties.get("got_v8_revision", ""),
          "parent_got_swarming_client_revision":
          build_properties.get("got_swarming_client_revision", ""),
          "parent_build_archive_url":
          build_properties.get("build_archive_url", ""),
          "parent_revision": build_properties.get("revision", ""),
          "parent_subordinatename": build_properties.get("subordinatename", ""),
          "parent_scheduler": build_properties.get("scheduler", ""),
          "parentname": build_properties.get("builderna", ""),
          "parent_buildnumber": build_properties.get("buildnumber", ""),
          "patchset": build_properties.get("patchset", ""),
          "issue": build_properties.get("issue", ""),
          "parent_try_job_key": build_properties.get("try_job_key", ""),
          "parent_got_webkit_revision": build_properties.get(
              "got_webkit_revision", ""),
          "parent_builddir": build_properties.get("builddir", ""),
          "parent_branch": build_properties.get("branch", ""),
          "parent_got_clang_revision": build_properties.get(
              "got_clang_revision", ""),
          "requester": build_properties.get("requester", ""),
          "parent_cr_revision": build_properties.get("got_revision", ""),
          "rietveld": build_properties.get("rietveld", ""),
          "parent_got_nacl_revision": build_properties.get("got_nacl_revision",
                                                           ""),
          "parent_buildername": build_properties.get("buildername", ""),
          "parent_got_revision": build_properties.get("got_revision", ""),
          "patch_url": build_properties.get("patch_url", ""),
          "parent_git_number": build_properties.get("git_number", ""),
          "parentsubordinatename": build_properties.get("subordinatename", ""),
          "root": build_properties.get("root", ""), }},
    ]
    api.trigger(*trigger_spec)


def Vista_Tests__dbg__2__steps(api):
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
           'GYP_CHROMIUM_NO_ACTION': '1',
           'LANDMINES_VERBOSE': '1',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': ' component=shared_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # extract build step
    api.python(
        "extract build",
        api.path["build"].join("scripts", "subordinate", "extract_build.py"),
        args=["--target", "Debug", "--build-archive-url", build_properties[
            "parent_build_archive_url"], '--build-properties=%s' %
              api.json.dumps(build_properties,
                             separators=(',', ':'))])
    # start crash handler step
    api.python("start crash handler",
               api.path["build"].join("scripts", "subordinate", "chromium",
                                      "run_crash_handler.py"),
               args=["--target", "Debug"])
    # runtest step
    api.python(
        "browser_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":"1",'+\
             '"GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'browser_tests',
         'browser_tests.exe', '--lib=browser_tests', '--gtest_print_time'])
    # runtest step
    api.python(
        "content_browsertests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_CHROMIUM_NO_ACTION":"1",'+\
             '"GYP_DEFINES":" component=shared_library",'+\
             '"LANDMINES_VERBOSE":"1"},"process_dumps":true,'+\
             '"start_crash_handler":true}',
         '--annotate=gtest', '--test-type', 'content_browsertests',
         'content_browsertests.exe', '--gtest_print_time'])
    # process dumps step
    api.python("process dumps",
               api.path["build"].join("scripts", "subordinate", "process_dumps.py"),
               args=["--target", "Debug"])


dispatch_directory = {
    'Vista Tests (dbg)(1)': Vista_Tests__dbg__1__steps,
    'Chromium Builder (dbg)': Chromium_Builder__dbg__steps,
    'Vista Tests (dbg)(2)': Vista_Tests__dbg__2__steps,
}


def RunSteps(api):
    if api.properties["buildername"] not in dispatch_directory:
        raise api.step.StepFailure("Builder unsupported by recipe.")
    else:
        dispatch_directory[api.properties["buildername"]](api)


def GenTests(api):
  yield (api.test('Vista_Tests__dbg__1_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Vista Tests (dbg)(1)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(parent_build_archive_url='abc') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Chromium_Builder__dbg_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Chromium Builder (dbg)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.step_data('zip build', api.json.output({'storage_url': 'abc',
      'zip_url': 'abc'})) +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Chromium_Builder__dbg_clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Chromium Builder (dbg)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(clobber='') +
    api.step_data('zip build', api.json.output({'storage_url': 'abc',
      'zip_url': 'abc'})) +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Vista_Tests__dbg__2_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Vista Tests (dbg)(2)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(parent_build_archive_url='abc') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
