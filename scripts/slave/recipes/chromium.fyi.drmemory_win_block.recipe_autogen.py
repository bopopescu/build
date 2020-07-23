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


def Windows_Tests__DrMemory__steps(api):
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
           'GYP_DEFINES': ' component=static_library'}
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
        args=["--target", "Release", "--build-archive-url", build_properties[
            "parent_build_archive_url"], '--build-properties=%s' %
              api.json.dumps(build_properties,
                             separators=(',', ':'))])
    with api.step.defer_results():
      # runtest step
      api.python(
          "memory test: webkit",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--run-shell-script', '--target', 'Release',
            "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           '--factory-properties={"blink_config":"chromium","gclient_env":'+\
               '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
               '"GYP_CHROMIUM_NO_ACTION":"1","GYP_DEFINES":'+\
               '" component=static_library","LANDMINES_VERBOSE":"1"},'+\
               '"halt_on_missing_build":true}',
           '--annotate=gtest', '--test-type', 'memory test: webkit',
           '--pass-build-dir', '--pass-target',
           r'../../../src\tools\valgrind\chrome_tests.bat', '--test', 'webkit',
           '--tool', 'drmemory_light'])
      # runtest step
      api.python(
          "memory test: webkit",
          api.path["build"].join("scripts", "subordinate", "runtest.py"),
          args=
          ['--run-shell-script', '--target', 'Release',
            "--build-properties=%s" %
           api.json.dumps(build_properties,
                          separators=(',', ':')),
           '--factory-properties={"blink_config":"chromium","gclient_env":'+\
               '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
               '"GYP_CHROMIUM_NO_ACTION":"1","GYP_DEFINES":'+\
               '" component=static_library","LANDMINES_VERBOSE":"1"},'+\
               '"halt_on_missing_build":true}',
           '--annotate=gtest', '--test-type', 'memory test: webkit',
           '--pass-build-dir', '--pass-target',
           r'../../../src\tools\valgrind\chrome_tests.bat', '--test', 'webkit',
           '--tool', 'drmemory_full'])


def Windows_Browser__DrMemory_light___1__steps(api):
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
           'GYP_DEFINES': ' component=static_library'}
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
        args=["--target", "Release", "--build-archive-url", build_properties[
            "parent_build_archive_url"], '--build-properties=%s' %
              api.json.dumps(build_properties,
                             separators=(',', ':'))])
    # runtest step
    api.python(
        "memory test: browser_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--run-shell-script', '--target', 'Release', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_CHROMIUM_NO_ACTION":"1","GYP_DEFINES":'+\
             '" component=static_library","LANDMINES_VERBOSE":"1"},'+\
             '"halt_on_missing_build":true,"retry_failed":false}',
         '--annotate=gtest', '--test-type',
         'memory test: browser_tests_1_of_2', '--pass-build-dir',
         '--pass-target', '--shard-index', '1', '--total-shards', '2',
         r'../../../src\tools\valgrind\chrome_tests.bat', '--test',
         'browser_tests', '--tool', 'drmemory_light'])


def Windows_Builder__DrMemory__steps(api):
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
           'GYP_DEFINES': 'build_for_tool=drmemory component=shared_library',
           'LANDMINES_VERBOSE': '1'}
    api.python("gclient runhooks wrapper",
               api.path["build"].join("scripts", "subordinate",
                                      "runhooks_wrapper.py"),
               env=env)
    # cleanup_temp step
    api.chromium.cleanup_temp()
    # compile.py step
    args = ['--solution', 'out.sln', '--target', 'Release',
            '--build-tool=ninja', '--', 'chromium_builder_dbg_drmemory_win']
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
        ["--json-urls", api.json.output(),
         "--target", "Release", '--build-url',
         'gs://chromium-build-transfer/drm-cr', '--build-properties=%s' %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium","build_url":'+\
             '"gs://chromium-build-transfer/drm-cr","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0"'+\
             ',"GYP_DEFINES":'+\
             '"build_for_tool=drmemory component=shared_library",'+\
             '"GYP_GENERATORS":"ninja","LANDMINES_VERBOSE":"1"},'+\
             '"package_pdb_files":true,"trigger":"chromium_windows_drmemory"}'
         ])
    if 'storage_url' in step_result.json.output:
      step_result.presentation.links['download'] =\
          step_result.json.output['storage_url']
    build_properties['build_archive_url'] = step_result.json.output['zip_url']
    # trigger step
    trigger_spec = [
        {'builder_name': 'Windows Tests (DrMemory)',
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
        {'builder_name': 'Windows Browser (DrMemory light) (1)',
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
        {'builder_name': 'Windows Browser (DrMemory light) (2)',
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


def Windows_Browser__DrMemory_light___2__steps(api):
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
           'GYP_DEFINES': ' component=static_library'}
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
        args=["--target", "Release", "--build-archive-url", build_properties[
            "parent_build_archive_url"], '--build-properties=%s' %
              api.json.dumps(build_properties,
                             separators=(',', ':'))])
    # runtest step
    api.python(
        "memory test: browser_tests",
        api.path["build"].join("scripts", "subordinate", "runtest.py"),
        args=
        ['--run-shell-script', '--target', 'Release', "--build-properties=%s" %
         api.json.dumps(build_properties,
                        separators=(',', ':')),
         '--factory-properties={"blink_config":"chromium","gclient_env":'+\
             '{"CHROMIUM_GYP_SYNTAX_CHECK":"1","DEPOT_TOOLS_UPDATE":"0",'+\
             '"GYP_CHROMIUM_NO_ACTION":"1","GYP_DEFINES":'+\
             '" component=static_library","LANDMINES_VERBOSE":"1"},'+\
             '"halt_on_missing_build":true,"retry_failed":false}',
         '--annotate=gtest', '--test-type',
         'memory test: browser_tests_2_of_2', '--pass-build-dir',
         '--pass-target', '--shard-index', '2', '--total-shards', '2',
         r'../../../src\tools\valgrind\chrome_tests.bat', '--test',
         'browser_tests', '--tool', 'drmemory_light'])


dispatch_directory = {
    'Windows Tests (DrMemory)': Windows_Tests__DrMemory__steps,
    'Windows Browser (DrMemory light) (1)':
    Windows_Browser__DrMemory_light___1__steps,
    'Windows Builder (DrMemory)': Windows_Builder__DrMemory__steps,
    'Windows Browser (DrMemory light) (2)':
    Windows_Browser__DrMemory_light___2__steps,
}


def RunSteps(api):
    if api.properties["buildername"] not in dispatch_directory:
        raise api.step.StepFailure("Builder unsupported by recipe.")
    else:
        dispatch_directory[api.properties["buildername"]](api)


def GenTests(api):
  yield (api.test('Windows_Tests__DrMemory_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows Tests (DrMemory)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(parent_build_archive_url='abc') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_Browser__DrMemory_light___1_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows Browser (DrMemory light) (1)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(parent_build_archive_url='abc') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_Builder__DrMemory_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows Builder (DrMemory)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.step_data('zip build', api.json.output({'storage_url': 'abc',
      'zip_url': 'abc'})) +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_Builder__DrMemory_clobber') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows Builder (DrMemory)') +
    api.properties(revision='123456789abcdef') +
    api.properties(got_revision='123456789abcdef') +
    api.properties(buildnumber='42') +
    api.properties(clobber='') +
    api.step_data('zip build', api.json.output({'storage_url': 'abc',
      'zip_url': 'abc'})) +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Windows_Browser__DrMemory_light___2_') +
    api.properties(mainname='chromium.fyi') +
    api.properties(buildername='Windows Browser (DrMemory light) (2)') +
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
