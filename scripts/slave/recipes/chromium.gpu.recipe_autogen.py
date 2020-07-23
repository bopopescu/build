# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'chromium',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

def Android_Debug__Nexus_9__steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
  soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
      'googlecode_url': 'http://%s.googlecode.com/svn',
      'nacl_trunk': 'http://src.chromium.org/native_client/trunk',
      'sourceforge_url': 'https://svn.code.sf.net/p/%(repo)s/code',
      'llvm_url': 'http://llvm.org/svn/llvm-project'}
  src_cfg.target_os = set(['android'])
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  api.bot_update.ensure_checkout(force=True)
  # gclient revert step
  api.gclient.revert()
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # subordinate_steps step
  api.python("subordinate_steps", "src/build/android/buildbot/bb_run_bot.py",
      args=['--build-properties=%s' % api.json.dumps(api.properties.legacy(),
                                                     separators=(',', ':')),
            '--factory-properties={"GYP_DEFINES":" component=shared_library",'+\
                '"android_bot_id":"gpu-builder-tests-dbg","clobber":false,'+\
                '"gclient_env":{},"gclient_timeout":3600,"target":"Debug",'+\
                '"target_os":"android"}'], allow_subannotations=True)


def Android_Debug__Nexus_5__steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
  soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
      'googlecode_url': 'http://%s.googlecode.com/svn',
      'nacl_trunk': 'http://src.chromium.org/native_client/trunk',
      'sourceforge_url': 'https://svn.code.sf.net/p/%(repo)s/code',
      'llvm_url': 'http://llvm.org/svn/llvm-project'}
  src_cfg.target_os = set(['android'])
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  api.bot_update.ensure_checkout(force=True)
  # gclient revert step
  api.gclient.revert()
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # subordinate_steps step
  api.python("subordinate_steps", "src/build/android/buildbot/bb_run_bot.py",
      args=['--build-properties=%s' % api.json.dumps(api.properties.legacy(),
                                                     separators=(',', ':')),
            '--factory-properties={"GYP_DEFINES":" component=shared_library",'+\
                '"android_bot_id":"gpu-builder-tests-dbg","clobber":false,'+\
                '"gclient_env":{},"gclient_timeout":3600,"target":"Debug",'+\
                '"target_os":"android"}'], allow_subannotations=True)


def Android_Debug__Nexus_6__steps(api):
  # update scripts step; implicitly run by recipe engine.
  # bot_update step
  src_cfg = api.gclient.make_config(GIT_MODE=True)
  soln = src_cfg.solutions.add()
  soln.name = "src"
  soln.url = "https://chromium.googlesource.com/chromium/src.git"
  soln.custom_deps = {'src/third_party/WebKit/LayoutTests': None}
  soln.custom_vars = {'webkit_trunk': 'http://src.chromium.org/blink/trunk',
      'googlecode_url': 'http://%s.googlecode.com/svn',
      'nacl_trunk': 'http://src.chromium.org/native_client/trunk',
      'sourceforge_url': 'https://svn.code.sf.net/p/%(repo)s/code',
      'llvm_url': 'http://llvm.org/svn/llvm-project'}
  src_cfg.target_os = set(['android'])
  src_cfg.got_revision_mapping.update({'src': 'got_revision',
    'src/third_party/WebKit': 'got_webkit_revision',
    'src/tools/swarming_client': 'got_swarming_client_revision',
    'src/v8': 'got_v8_revision'})
  api.gclient.c = src_cfg
  api.bot_update.ensure_checkout(force=True)
  # gclient revert step
  api.gclient.revert()
  # cleanup_temp step
  api.chromium.cleanup_temp()
  # subordinate_steps step
  api.python("subordinate_steps", "src/build/android/buildbot/bb_run_bot.py",
      args=['--build-properties=%s' % api.json.dumps(api.properties.legacy(),
                                                     separators=(',', ':')),
            '--factory-properties={"GYP_DEFINES":" component=shared_library",'+\
                '"android_bot_id":"gpu-builder-tests-dbg","clobber":false,'+\
                '"gclient_env":{},"gclient_timeout":3600,"target":"Debug",'+\
                '"target_os":"android"}'], allow_subannotations=True)


dispatch_directory = {
  'Android Debug (Nexus 9)': Android_Debug__Nexus_9__steps,
  'Android Debug (Nexus 5)': Android_Debug__Nexus_5__steps,
  'Android Debug (Nexus 6)': Android_Debug__Nexus_6__steps,
}


def RunSteps(api):
  if api.properties["buildername"] not in dispatch_directory:
    raise api.step.StepFailure("Builder unsupported by recipe.")
  else:
    dispatch_directory[api.properties["buildername"]](api)

def GenTests(api):
  yield (api.test('Android_Debug__Nexus_9_') +
    api.properties(mainname='chromium.gpu') +
    api.properties(buildername='Android Debug (Nexus 9)') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Android_Debug__Nexus_5_') +
    api.properties(mainname='chromium.gpu') +
    api.properties(buildername='Android Debug (Nexus 5)') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('Android_Debug__Nexus_6_') +
    api.properties(mainname='chromium.gpu') +
    api.properties(buildername='Android Debug (Nexus 6)') +
    api.properties(subordinatename='TestSubordinate')
        )
  yield (api.test('builder_not_in_dispatch_directory') +
    api.properties(mainname='chromium.gpu') +
    api.properties(buildername='nonexistent_builder') +
    api.properties(subordinatename='TestSubordinate')
        )
