# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/gclient',
  'depot_tools/bot_update',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

from recipe_engine.recipe_api import Property

PROPERTIES = {
  'xfa': Property(default=False, kind=bool),
  'memory_tool': Property(default=None, kind=str),
  'v8': Property(default=True, kind=bool),
  "win64": Property(default=False, kind=bool),
  "clang": Property(default=False, kind=bool),
}


def _MakeGypDefines(gyp_defines):
  return ' '.join(['%s=%s' % (key, str(value)) for key, value in
                   gyp_defines.iteritems()])


def _CheckoutSteps(api, memory_tool, xfa, v8, win64, clang):
  # Checkout pdfium and its dependencies (specified in DEPS) using gclient
  api.gclient.set_config('pdfium')
  api.bot_update.ensure_checkout(force=True)

  gyp_defines = {
      'pdf_enable_v8': int(v8),
      'pdf_enable_xfa': int(xfa),
  }

  if memory_tool == 'asan':
    gyp_defines['asan'] = 1

  if clang:
    gyp_defines['clang'] = 1

  if win64:
    gyp_defines['target_arch'] = 'x64'

  env = {
      'GYP_DEFINES': _MakeGypDefines(gyp_defines)
  }
  api.gclient.runhooks(env=env)


def _BuildSteps(api, out_dir):
  # Build sample file using Ninja
  debug_path = api.path['checkout'].join('out', out_dir)
  api.step('compile with ninja', ['ninja', '-C', debug_path])


def _RunDrMemoryTests(api, v8):
  pdfium_tests_py = str(api.path['checkout'].join('tools',
                                                  'drmemory',
                                                  'scripts',
                                                  'pdfium_tests.py'))
  api.python('unittests', pdfium_tests_py,
             args=['--test', 'pdfium_unittests'],
             cwd=api.path['checkout'])
  api.python('embeddertests', pdfium_tests_py,
             args=['--test', 'pdfium_embeddertests'],
             cwd=api.path['checkout'])
  if v8:
    api.python('javascript tests', pdfium_tests_py,
               args=['--test', 'pdfium_javascript'],
               cwd=api.path['checkout'])
  api.python('pixel tests', pdfium_tests_py,
             args=['--test', 'pdfium_pixel'],
             cwd=api.path['checkout'])
  api.python('corpus tests', pdfium_tests_py,
             args=['--test', 'pdfium_corpus'],
             cwd=api.path['checkout'])


def _RunTests(api, memory_tool, v8, out_dir):
  if memory_tool == 'drmemory':
    _RunDrMemoryTests(api, v8)
    return

  env = {}
  if memory_tool == 'asan':
    # TODO(ochang): Once PDFium is less leaky, remove the detect_leaks flag.
    env.update({
        'ASAN_OPTIONS': 'detect_leaks=0:allocator_may_return_null=1'})

  unittests_path = str(api.path['checkout'].join('out', out_dir,
                                                 'pdfium_unittests'))
  if api.platform.is_win:
    unittests_path += '.exe'
  api.step('unittests', [unittests_path], cwd=api.path['checkout'], env=env)

  embeddertests_path = str(api.path['checkout'].join('out', out_dir,
                                                     'pdfium_embeddertests'))
  if api.platform.is_win:
    embeddertests_path += '.exe'
  api.step('embeddertests', [embeddertests_path],
           cwd=api.path['checkout'],
           env=env)

  script_args = ['--build-dir', api.path.join('out', out_dir)]

  if v8:
    javascript_path = str(api.path['checkout'].join('testing', 'tools',
                                                    'run_javascript_tests.py'))
    api.python('javascript tests', javascript_path, script_args,
               cwd=api.path['checkout'], env=env)

  pixel_tests_path = str(api.path['checkout'].join('testing', 'tools',
                                                   'run_pixel_tests.py'))
  api.python('pixel tests', pixel_tests_path, script_args,
             cwd=api.path['checkout'], env=env)

  corpus_tests_path = str(api.path['checkout'].join('testing', 'tools',
                                                    'run_corpus_tests.py'))
  api.python('corpus tests', corpus_tests_path, script_args,
             cwd=api.path['checkout'], env=env)


def RunSteps(api, memory_tool, xfa, v8, win64, clang):
  _CheckoutSteps(api, memory_tool, xfa, v8, win64, clang)

  if win64:
    out_dir = 'Debug_x64'
  else:
    out_dir = 'Debug'

  _BuildSteps(api, out_dir)
  with api.step.defer_results():
    _RunTests(api, memory_tool, v8, out_dir)


def GenTests(api):
  yield (
      api.test('win') +
      api.platform('win', 64) +
      api.properties(mainname="client.pdfium",
                     buildername='windows',
                     subordinatename="test_subordinate")
  )
  yield (
      api.test('linux') +
      api.platform('linux', 64) +
      api.properties(mainname="client.pdfium",
                     buildername='linux',
                     subordinatename="test_subordinate")
  )
  yield (
      api.test('mac') +
      api.platform('mac', 64) +
      api.properties(mainname="client.pdfium",
                     buildername='mac',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('win_no_v8') +
      api.platform('win', 64) +
      api.properties(v8=False,
                     mainname="client.pdfium",
                     buildername='windows',
                     subordinatename="test_subordinate")
  )
  yield (
      api.test('linux_no_v8') +
      api.platform('linux', 64) +
      api.properties(v8=False,
                     mainname="client.pdfium",
                     buildername='linux',
                     subordinatename="test_subordinate")
  )
  yield (
      api.test('mac_no_v8') +
      api.platform('mac', 64) +
      api.properties(v8=False,
                     mainname="client.pdfium",
                     buildername='mac',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('win_xfa') +
      api.platform('win', 64) +
      api.properties(xfa=True,
                     mainname="client.pdfium",
                     buildername='windows_xfa',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('win_xfa_64') +
      api.platform('win', 64) +
      api.properties(xfa=True,
                     win64=True,
                     mainname="client.pdfium",
                     buildername='windows_xfa_64',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('win_xfa_clang') +
      api.platform('win', 64) +
      api.properties(xfa=True,
                     clang=True,
                     mainname="client.pdfium",
                     buildername='windows_xfa_clang',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('win_xfa_clang_x64') +
      api.platform('win', 64) +
      api.properties(xfa=True,
                     clang=True,
                     win64=True,
                     mainname="client.pdfium",
                     buildername='windows_xfa_clang_x64',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('linux_xfa') +
      api.platform('linux', 64) +
      api.properties(xfa=True,
                     mainname="client.pdfium",
                     buildername='linux_xfa',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('mac_xfa') +
      api.platform('mac', 64) +
      api.properties(xfa=True,
                     mainname="client.pdfium",
                     buildername='mac_xfa',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('linux_asan') +
      api.platform('linux', 64) +
      api.properties(memory_tool='asan',
                     mainname="client.pdfium",
                     buildername='linux_asan',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('drm_win_xfa') +
      api.platform('win', 64) +
      api.properties(xfa=True,
                     memory_tool='drmemory',
                     mainname="client.pdfium",
                     buildername='drm_win_xfa',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('linux_xfa_asan') +
      api.platform('linux', 64) +
      api.properties(xfa=True,
                     memory_tool='asan',
                     mainname="client.pdfium",
                     buildername='linux_xfa_asan',
                     subordinatename="test_subordinate")
  )

  yield (
      api.test('try-linux_xfa_asan') +
      api.platform('linux', 64) +
      api.properties.tryserver(mainname='tryserver.client.pdfium',
                               buildername='linux_xfa_asan')
  )
