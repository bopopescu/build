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


def ChromiumOS_Linux_Tests_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
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
           'GYP_DEFINES': ' component=shared_library'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Debug']
    if "clobber" in api.properties:
        args.append("--clobber")
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # runtest step
    api.python(
        "sync_integration_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--target', 'Debug', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         ('--factory-properties={"blink_config":"chromium","gclient_env":'
          '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
          '"GYP_DEFINES":" component=shared_library","LANDMINES_VERBOSE":"1"},'
          '"generate_gtest_json":true,"test_results_server":'
          '"test-results.appspot.com"}'), '--annotate=gtest', '--test-type',
         'sync_integration_tests', '--generate-json-file', '-o',
         'gtest-results/sync_integration_tests', '--build-number',
         api.properties["buildnumber"], '--builder-name', api.properties[
             "buildername"], 'sync_integration_tests',
         '--ui-test-action-max-timeout=120000', '--gtest_print_time'])


def Android_ChromeDriver_Tests__dbg__steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "src"
    soln.url = "https://chromium.googlesource.com/chromium/src.git"
    soln.custom_deps = {
        'src/chrome/test/chromedriver/third_party/java_tests':
        'https://chromium.googlesource.com/chromium/deps/webdriver.git',
        'src/third_party/WebKit/LayoutTests': None
    }
    soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
                        'googlecode_url': 'http://%s.googlecode.com/svn',
                        'nacl_trunk':
                        'http://src.chromium.org/native_client/trunk',
                        'sourceforge_url':
                        'https://svn.code.sf.net/p/%(repo)s/code',
                        'llvm_url': 'http://llvm.org/svn/llvm-project'}
    src_cfg.target_os = set(['android'])
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
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # subordinate_steps step
    api.python(
        "subordinate_steps",
        "src/build/android/buildbot/bb_run_bot.py",
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         ('--factory-properties={"GYP_DEFINES":" component=shared_library",'
          '"android_bot_id":"chromedriver-fyi-tests-dbg","build_url":'
          '"gs://chromium-fyi-archive/chromium.fyi/Android Builder (dbg)",'
          '"clobber":false,"gclient_env":{},"target":"Debug",'
          '"target_os":"android"}')],
        allow_subannotations=True)


def Blink_Linux_LSan_ASan_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
    # bot_update step
    src_cfg = api.gclient.make_config(GIT_MODE=True)
    soln = src_cfg.solutions.add()
    soln.name = "src"
    soln.url = "https://chromium.googlesource.com/chromium/src.git"
    soln.custom_deps = {}
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
           'GYP_DEFINES': 'asan=1 lsan=1 component=static_library',
           'LANDMINES_VERBOSE': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # update_clang step; generic ShellCommand converted
    api.step("update_clang",
             ['python', 'src/tools/clang/scripts/update.py'],
             env={'LLVM_URL': 'http://llvm.org/svn/llvm-project'},
             cwd=api.path["subordinate_build"])
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--build-tool=ninja',
            '--compiler=goma-clang', '--', 'blink_tests']
    if "clobber" in api.properties:
        args.append("--clobber")
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # runtest step
    api.python(
        "webkit_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--run-python-script', '--target', 'Release', "--build-properties=%s"
         % api.json.dumps(build_properties,
                          separators=(',', ':')),
         ('--factory-properties={"additional_expectations":'
          '[["third_party","WebKit","LayoutTests","ASANExpectations"]],'
          '"archive_webkit_results":false,"asan":true,"blink_config":"blink",'
          '"gclient_env":{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE"'
          ':"0","GYP_DEFINES":"asan=1 lsan=1 component=static_library",'
          '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"},'
          '"generate_gtest_json":true,"lsan":true,"time_out_ms":"48000",'
          '"webkit_dir":"third_party/WebKit/Source","webkit_test_options":'
          '["--enable-sanitizer"]}'), '--no-xvfb', api.path["build"].join(
              "scripts", "subordinate", "chromium", "layout_test_wrapper.py"),
         '--target', 'Release', '-o', '../../layout-test-results',
         '--build-number', api.properties["buildnumber"], '--builder-name',
         api.properties["buildername"], '--additional-expectations',
         'src/third_party/WebKit/LayoutTests/ASANExpectations',
         '--time-out-ms', '48000', '--options=--enable-sanitizer'])


def Android_Asan_Builder_Tests__dbg__steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
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
    src_cfg.target_os = set(['android'])
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
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # subordinate_steps step
    api.python(
        "subordinate_steps",
        "src/build/android/buildbot/bb_run_bot.py",
        args=
        ['--build-properties=%s' % api.json.dumps(build_properties,
                                                  separators=(',', ':')),
         ('--factory-properties={"GYP_DEFINES":" component=shared_library",'
          '"android_bot_id":"asan-builder-tests-dbg","clobber":false,'
          '"gclient_env":{},"target":"Debug","target_os":"android"}')],
        allow_subannotations=True)


def CFI_Linux_CF_steps(api):
    build_properties = api.properties.legacy()
    # update scripts step; implicitly run by recipe engine.
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
           'GYP_DEFINES': ' component=static_library',
           'LLVM_DOWNLOAD_GOLD_PLUGIN': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--target', 'Release', '--clobber', 'chromium_builder_asan']
    api.python("compile",
               api.path["build"].join("scripts", "subordinate", "compile.py"),
               args=args)
    # ClusterFuzz Archive step
    # HACK(aneeshm): chromium_utils fails without this.
    build_properties["primary_repo"] = ""
    api.python(
        'ClusterFuzz Archive',
        api.path["build"].join("scripts", "subordinate", "chromium",
                               "cf_archive_build.py"),
        args=
        ['--target', 'Release', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         ('--factory-properties={"blink_config":"chromium","cf_archive_build":'
          'true,"cf_archive_name":"cfi","gclient_env":'
          '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'
          '"GYP_DEFINES":" component=static_library","LANDMINES_VERBOSE":"1",'
          '"LLVM_DOWNLOAD_GOLD_PLUGIN":"1"},"gs_acl":"public-read",'
          '"gs_bucket":"gs://chromium-browser-cfi"}')],
        cwd=api.path["subordinate_build"])


dispatch_directory = {
    'ChromiumOS Linux Tests': ChromiumOS_Linux_Tests_steps,
    'Android ChromeDriver Tests (dbg)': Android_ChromeDriver_Tests__dbg__steps,
    'Blink Linux LSan ASan': Blink_Linux_LSan_ASan_steps,
    'Android Asan Builder Tests (dbg)': Android_Asan_Builder_Tests__dbg__steps,
    'CFI Linux CF': CFI_Linux_CF_steps,
}


def RunSteps(api):
    if api.properties["buildername"] not in dispatch_directory:
        raise api.step.StepFailure("Builder unsupported by recipe.")
    else:
        dispatch_directory[api.properties["buildername"]](api)


def GenTests(api):
  yield (api.test('ChromiumOS_Linux_Tests') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='ChromiumOS Linux Tests') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('ChromiumOS_Linux_Tests_clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='ChromiumOS Linux Tests') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(clobber='') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Android_ChromeDriver_Tests__dbg_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Android ChromeDriver Tests (dbg)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Blink_Linux_LSan_ASan') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Blink Linux LSan ASan') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Blink_Linux_LSan_ASan_clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Blink Linux LSan ASan') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(clobber='') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Android_Asan_Builder_Tests__dbg_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Android Asan Builder Tests (dbg)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('CFI_Linux_CF') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='CFI Linux CF') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
