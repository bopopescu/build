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


def linux_sdk_multi_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "src"
    soln.url = "https://chromium.googlesource.com/chromium/src.git"
    soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'nacl_trunk':
                        'svn://svn.chromium.org/native_client/trunk',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'llvm_url': 'svn://svn.chromium.org/llvm-project'}
    soln = src_cfg.solutions.add()
    soln.name = "src-internal"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
    soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
                        'src/tools/grit/grit/test/data': None,
                        'src/chrome/test/data/firefox3_searchplugins': None,
                        'src/webkit/data/test_shell/plugins': None,
                        'src/data/page_cycler': None,
                        'src/data/mozilla_js_tests': None,
                        'src/chrome/test/data/firefox2_profile/searchplugins':
                        None,
                        'src/data/esctf': None,
                        'src/data/memory_test': None,
                        'src/data/mach_ports': None,
                        'src/webkit/data/xbm_decoder': None,
                        'src/webkit/data/ico_decoder': None,
                        'src/data/selenium_core': None,
                        'src/chrome/test/data/ssl/certs': None,
                        'src/chrome/test/data/osdd': None,
                        'src/webkit/data/bmp_decoder': None,
                        'src/chrome/test/data/firefox3_profile/searchplugins':
                        None,
                        'src/data/autodiscovery': None}
    soln.custom_vars = {}
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
           'GYP_DEFINES': 'fastbuild=1 component=static_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--clobber', '--compiler=goma',
            'chromium_builder_nacl_sdk']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium",'+\
             '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1",'+\
             '"DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":'+\
             '"fastbuild=1 component=static_library","LANDMINES_VERBOSE":"1"'+\
             '},"no_gclient_branch":true,"nuke_and_pave":false}'
         ],
        allow_subannotations=True)


def mac_sdk_multi_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "src"
    soln.url = "https://chromium.googlesource.com/chromium/src.git"
    soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'nacl_trunk':
                        'svn://svn.chromium.org/native_client/trunk',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'llvm_url': 'svn://svn.chromium.org/llvm-project'}
    soln = src_cfg.solutions.add()
    soln.name = "src-internal"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
    soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
                        'src/tools/grit/grit/test/data': None,
                        'src/chrome/test/data/firefox3_searchplugins': None,
                        'src/webkit/data/test_shell/plugins': None,
                        'src/data/page_cycler': None,
                        'src/data/mozilla_js_tests': None,
                        'src/chrome/test/data/firefox2_profile/searchplugins':
                        None,
                        'src/data/esctf': None,
                        'src/data/memory_test': None,
                        'src/data/mach_ports': None,
                        'src/webkit/data/xbm_decoder': None,
                        'src/webkit/data/ico_decoder': None,
                        'src/data/selenium_core': None,
                        'src/chrome/test/data/ssl/certs': None,
                        'src/chrome/test/data/osdd': None,
                        'src/webkit/data/bmp_decoder': None,
                        'src/chrome/test/data/firefox3_profile/searchplugins':
                        None,
                        'src/data/autodiscovery': None}
    soln.custom_vars = {}
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
           'GYP_DEFINES': 'fastbuild=1 component=static_library',
           'LANDMINES_VERBOSE': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--clobber', '--build-tool=ninja',
            '--compiler=goma-clang', '--', 'chromium_builder_nacl_sdk']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_DEFINES":"fastbuild=1 component=static_library",'+\
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"},'+\
             '"no_gclient_branch":true,"nuke_and_pave":false}'
         ],
        allow_subannotations=True)


def windows_sdk_multi_steps(api):
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
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'nacl_trunk':
                        'svn://svn.chromium.org/native_client/trunk',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'llvm_url': 'svn://svn.chromium.org/llvm-project'}
    soln = src_cfg.solutions.add()
    soln.name = "src-internal"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/src-internal"
    soln.custom_deps = {'src/chrome/test/data/firefox2_searchplugins': None,
                        'src/tools/grit/grit/test/data': None,
                        'src/chrome/test/data/firefox3_searchplugins': None,
                        'src/webkit/data/test_shell/plugins': None,
                        'src/data/page_cycler': None,
                        'src/data/mozilla_js_tests': None,
                        'src/chrome/test/data/firefox2_profile/searchplugins':
                        None,
                        'src/data/esctf': None,
                        'src/data/memory_test': None,
                        'src/data/mach_ports': None,
                        'src/webkit/data/xbm_decoder': None,
                        'src/webkit/data/ico_decoder': None,
                        'src/data/selenium_core': None,
                        'src/chrome/test/data/ssl/certs': None,
                        'src/chrome/test/data/osdd': None,
                        'src/webkit/data/bmp_decoder': None,
                        'src/chrome/test/data/firefox3_profile/searchplugins':
                        None,
                        'src/data/autodiscovery': None}
    soln.custom_vars = {}
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
           'GYP_DEFINES': 'fastbuild=1 component=static_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'all.sln', '--project', 'chromium_builder_nacl_sdk',
            '--target', 'Release', '--clobber', '--compiler=goma']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_DEFINES":"fastbuild=1 component=static_library",'+\
             '"LANDMINES_VERBOSE":"1"},"no_gclient_branch":true,'+\
             '"nuke_and_pave":false}'
         ],
        allow_subannotations=True)


def linux_sdk_multirel_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "chrome-official"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/tools/buildspec/"+\
        "build/chrome-official"
    soln.custom_deps = {'src-pdf': None, 'src/pdf': None}
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'svn_url': 'svn://svn.chromium.org'}
    src_cfg.got_revision_mapping.update(
        {'src': 'got_revision',
         'src/third_party/WebKit': 'got_webkit_revision',
         'src/tools/swarming_client': 'got_swarming_client_revision',
         'src/v8': 'got_v8_revision'})
    api.gclient.c = src_cfg
    result = api.bot_update.ensure_checkout(force=True)
    build_properties.update(result.json.output.get("properties", {}))
    # unnamed step; null converted
    # gclient runhooks wrapper step
    env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1',
           'LANDMINES_VERBOSE': '1',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': 'fastbuild=1 component=static_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--clobber', '--compiler=goma',
            'chromium_builder_tests']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_DEFINES":"fastbuild=1 component=static_library",'+\
             '"LANDMINES_VERBOSE":"1"},"no_gclient_branch":true,'+\
             '"nuke_and_pave":true}'
         ],
        allow_subannotations=True)


def windows_sdk_multirel_steps(api):
    build_properties = api.properties.legacy()
    # svnkill step; not necessary in recipes
    # update scripts step; implicitly run by recipe engine.
    # taskkill step
    api.python("taskkill", api.path["build"].join("scripts", "subordinate",
                                                  "kill_processes.py"))
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "chrome-official"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/tools/buildspec/"+\
        "build/chrome-official"
    soln.custom_deps = {'src-pdf': None, 'src/pdf': None}
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'svn_url': 'svn://svn.chromium.org'}
    src_cfg.got_revision_mapping.update(
        {'src': 'got_revision',
         'src/third_party/WebKit': 'got_webkit_revision',
         'src/tools/swarming_client': 'got_swarming_client_revision',
         'src/v8': 'got_v8_revision'})
    api.gclient.c = src_cfg
    result = api.bot_update.ensure_checkout(force=True)
    build_properties.update(result.json.output.get("properties", {}))
    # unnamed step; null converted
    # gclient runhooks wrapper step
    env = {'CHROMIUM_GYP_SYNTAX_CHECK': '1',
           'LANDMINES_VERBOSE': '1',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': 'fastbuild=1 component=static_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'all.sln', '--project', 'chromium_builder_tests',
            '--target', 'Release', '--clobber', '--compiler=goma']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_DEFINES":"fastbuild=1 component=static_library",'+\
             '"LANDMINES_VERBOSE":"1"},"no_gclient_branch":true,'+\
             '"nuke_and_pave":true}'
         ],
        allow_subannotations=True)


def mac_sdk_multirel_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "chrome-official"
    soln.url = "svn://svn.chromium.org/chrome-internal/trunk/tools/buildspec/"+\
        "build/chrome-official"
    soln.custom_deps = {'src-pdf': None, 'src/pdf': None}
    soln.custom_vars = {'webkit_trunk': 'svn://svn.chromium.org/blink/trunk',
                        'googlecode_url': 'svn://svn.chromium.org/%s',
                        'sourceforge_url': 'svn://svn.chromium.org/%(repo)s',
                        'svn_url': 'svn://svn.chromium.org'}
    src_cfg.got_revision_mapping.update(
        {'src': 'got_revision',
         'src/third_party/WebKit': 'got_webkit_revision',
         'src/tools/swarming_client': 'got_swarming_client_revision',
         'src/v8': 'got_v8_revision'})
    api.gclient.c = src_cfg
    result = api.bot_update.ensure_checkout(force=True)
    build_properties.update(result.json.output.get("properties", {}))
    # unnamed step; null converted
    # gclient runhooks wrapper step
    env = {'LANDMINES_VERBOSE': '1',
           'GYP_GENERATORS': 'ninja',
           'DEPOT_TOOLS_UPDATE': '0',
           'GYP_DEFINES': 'fastbuild=1 component=static_library',
           'CHROMIUM_GYP_SYNTAX_CHECK': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--clobber', '--build-tool=ninja',
            '--compiler=goma-clang', '--', 'chromium_builder_tests']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # annotated_steps step
    api.python(
        "annotated_steps",
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "nacl_sdk_buildbot_run.py"),
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         '--factory-properties={"annotated_script":"nacl_sdk_buildbot_run.py"'+\
             ',"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_DEFINES":"fastbuild=1 component=static_library",'+\
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"},'+\
             '"no_gclient_branch":true,"nuke_and_pave":true}'
         ],
        allow_subannotations=True)


dispatch_directory = {
    'linux-sdk-multi': linux_sdk_multi_steps,
    'mac-sdk-multi': mac_sdk_multi_steps,
    'windows-sdk-multi': windows_sdk_multi_steps,
    'linux-sdk-multirel': linux_sdk_multirel_steps,
    'linux-sdk-asan-multi': linux_sdk_multi_steps,
    'windows-sdk-multirel': windows_sdk_multirel_steps,
    'mac-sdk-multirel': mac_sdk_multirel_steps,
}


def RunSteps(api):
    if api.properties["buildername"] not in dispatch_directory:
        raise api.step.StepFailure("Builder unsupported by recipe.")
    else:
        dispatch_directory[api.properties["buildername"]](api)


def GenTests(api):
    yield (api.test('linux_sdk_multi') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='linux-sdk-multi') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('mac_sdk_multi') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='mac-sdk-multi') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('windows_sdk_multi') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='windows-sdk-multi') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('linux_sdk_multirel') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='linux-sdk-multirel') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('linux_sdk_asan_multi') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='linux-sdk-asan-multi') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('windows_sdk_multirel') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='windows-sdk-multirel') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('mac_sdk_multirel') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='mac-sdk-multirel') +
           api.properties(revision='123456789abcdef') + api.properties(
               got_revision='123456789abcdef') + api.properties(
                   buildnumber='42') + api.properties(subordinatename='TestSubordinate'))
    yield (api.test('builder_not_in_dispatch_directory') + api.properties(
        mainname='client.nacl.sdk') + api.properties(
            buildername='nonexistent_builder') + api.properties(
                subordinatename='TestSubordinate'))
