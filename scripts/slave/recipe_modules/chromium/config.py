# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pipes

from slave.recipe_config import config_item_context, ConfigGroup
from slave.recipe_config import Dict, List, Single, Static, Set, BadConf
from slave.recipe_config_types import Path

# Because of the way that we use decorators, pylint can't figure out the proper
# type signature of functions annotated with the @config_ctx decorator.
# pylint: disable=E1123

HOST_PLATFORMS = ('linux', 'win', 'mac')
TARGET_PLATFORMS = HOST_PLATFORMS + ('ios', 'android', 'chromeos')
HOST_TARGET_BITS = (32, 64)
HOST_ARCHS = ('intel',)
TARGET_ARCHS = HOST_ARCHS + ('arm', 'mipsel')
TARGET_CROS_BOARDS = (None, 'x86-generic')
BUILD_CONFIGS = ('Release', 'Debug', 'Coverage')
MEMORY_TOOLS = ('memcheck', 'drmemory_full', 'drmemory_light')
PROJECT_GENERATORS = ('gyp', 'gn')

def check(val, potentials):
  assert val in potentials
  return val

# Schema for config items in this module.
def BaseConfig(HOST_PLATFORM, HOST_ARCH, HOST_BITS,
               TARGET_PLATFORM, TARGET_ARCH, TARGET_BITS,
               BUILD_CONFIG, TARGET_CROS_BOARD, **_kwargs):
  equal_fn = lambda tup: ('%s=%s' % (tup[0], pipes.quote(str(tup[1]))))
  return ConfigGroup(
    compile_py = ConfigGroup(
      default_targets = Set(basestring),
      build_tool = Single(basestring),
      cross_tool = Single(basestring, required=False),
      compiler = Single(basestring, required=False),
      mode = Single(basestring, required=False),
      goma_dir = Single(Path, required=False),
      clobber = Single(bool, empty_val=False, required=False, hidden=False),
      pass_arch_flag = Single(bool, empty_val=False, required=False),
      xcode_sdk = Single(basestring, required=False),
      xcode_project = Single(Path, required=False),
      solution = Single(Path, required=False),
    ),
    gyp_env = ConfigGroup(
      GYP_CROSSCOMPILE = Single(int, jsonish_fn=str, required=False),
      GYP_CHROMIUM_NO_ACTION = Single(int, jsonish_fn=str, required=False),
      GYP_DEFINES = Dict(equal_fn, ' '.join, (basestring,int,Path)),
      GYP_GENERATORS = Set(basestring, ','.join),
      GYP_GENERATOR_FLAGS = Dict(equal_fn, ' '.join, (basestring,int)),
      GYP_MSVS_VERSION = Single(basestring, required=False),
      GYP_USE_SEPARATE_MSPDBSRV = Single(int, jsonish_fn=str, required=False),
    ),
    project_generator = ConfigGroup(
      tool = Single(basestring, empty_val='gyp'),
      args = Set(basestring),
    ),
    build_dir = Single(Path),
    cros_sdk_args = List(basestring),
    runtests = ConfigGroup(
      memory_tool = Single(basestring, required=False),
      memory_tests_runner = Single(Path),
      lsan_suppressions_file = Single(Path),
      test_args = List(basestring),
    ),

    # Some platforms do not have a 1:1 correlation of BUILD_CONFIG to what is
    # passed as --target on the command line.
    build_config_fs = Single(basestring),

    BUILD_CONFIG = Static(check(BUILD_CONFIG, BUILD_CONFIGS)),

    HOST_PLATFORM = Static(check(HOST_PLATFORM, HOST_PLATFORMS)),
    HOST_ARCH = Static(check(HOST_ARCH, HOST_ARCHS)),
    HOST_BITS = Static(check(HOST_BITS, HOST_TARGET_BITS)),

    TARGET_PLATFORM = Static(check(TARGET_PLATFORM, TARGET_PLATFORMS)),
    TARGET_ARCH = Static(check(TARGET_ARCH, TARGET_ARCHS)),
    TARGET_BITS = Static(check(TARGET_BITS, HOST_TARGET_BITS)),
    TARGET_CROS_BOARD = Static(TARGET_CROS_BOARD),

    gn_args = List(basestring),
  )

TEST_FORMAT = (
  '%(BUILD_CONFIG)s-'
  '%(HOST_PLATFORM)s.%(HOST_ARCH)s.%(HOST_BITS)s'
  '-to-'
  '%(TARGET_PLATFORM)s.%(TARGET_ARCH)s.%(TARGET_BITS)s'
)

# Used by the test harness to inspect and generate permutations for this
# config module.  {varname -> [possible values]}
VAR_TEST_MAP = {
  'HOST_PLATFORM':   HOST_PLATFORMS,
  'HOST_ARCH':       HOST_ARCHS,
  'HOST_BITS':       HOST_TARGET_BITS,

  'TARGET_PLATFORM': TARGET_PLATFORMS,
  'TARGET_ARCH':     TARGET_ARCHS,
  'TARGET_BITS':     HOST_TARGET_BITS,
  'TARGET_CROS_BOARD': TARGET_CROS_BOARDS,

  'BUILD_CONFIG':    BUILD_CONFIGS,
}
config_ctx = config_item_context(BaseConfig, VAR_TEST_MAP, TEST_FORMAT)


@config_ctx(is_root=True)
def BASE(c):
  host_targ_tuples = [(c.HOST_PLATFORM, c.HOST_ARCH, c.HOST_BITS),
                      (c.TARGET_PLATFORM, c.TARGET_ARCH, c.TARGET_BITS)]

  for (plat, arch, bits) in host_targ_tuples:
    if plat == 'ios':
      if arch not in ('arm', 'intel'):
        raise BadConf('%s/%s arch is not supported on %s' % (arch, bits, plat))
    elif plat in ('win', 'mac'):
      if arch != 'intel':
        raise BadConf('%s arch is not supported on %s' % (arch, plat))
    elif plat in ('chromeos', 'android', 'linux'):
      pass  # no arch restrictions
    else:  # pragma: no cover
      assert False, "Not covering a platform: %s" % plat

  potential_platforms = {
    # host -> potential target platforms
    'win':   ('win',),
    'mac':   ('mac', 'ios'),
    'linux': ('linux', 'chromeos', 'android'),
  }.get(c.HOST_PLATFORM)

  if not potential_platforms:  # pragma: no cover
    raise BadConf('Cannot build on "%s"' % c.HOST_PLATFORM)

  if c.TARGET_PLATFORM not in potential_platforms:
    raise BadConf('Can not compile "%s" on "%s"' %
                  (c.TARGET_PLATFORM, c.HOST_PLATFORM))

  if c.TARGET_CROS_BOARD:
    if not c.TARGET_PLATFORM == 'chromeos':
      raise BadConf("Cannot specify CROS board for non-'chromeos' platform")

  if c.HOST_PLATFORM != c.TARGET_PLATFORM or c.HOST_ARCH != c.TARGET_ARCH:
    c.gyp_env.GYP_CROSSCOMPILE = 1

  if c.HOST_BITS < c.TARGET_BITS:
    raise BadConf('host bits < targ bits')

  c.build_config_fs = c.BUILD_CONFIG
  if c.HOST_PLATFORM == 'win':
    if c.TARGET_BITS == 64:
      # Windows requires 64-bit builds to be in <dir>_x64.
      c.build_config_fs = c.BUILD_CONFIG + '_x64'

  # Test runner memory tools that are not compile-time based.
  c.runtests.memory_tests_runner = Path('[CHECKOUT]', 'tools', 'valgrind',
                                        'chrome_tests',
                                        platform_ext={'win': '.bat',
                                                      'mac': '.sh',
                                                      'linux': '.sh'})

  if c.project_generator.tool not in PROJECT_GENERATORS:  # pragma: no cover
    raise BadConf('"%s" is not a supported project generator tool, the '
                  'supported ones are: %s' % (c.project_generator.tool,
                                              ','.join(PROJECT_GENERATORS)))
  gyp_arch = {
    ('intel', 32): 'ia32',
    ('intel', 64): 'x64',
    ('arm',   32): 'arm',
    ('arm',   64): 'arm64',
    ('mipsel',  32): 'mipsel',
    ('mipsel',  64): 'mipsel',
  }.get((c.TARGET_ARCH, c.TARGET_BITS))
  if gyp_arch:
    c.gyp_env.GYP_DEFINES['target_arch'] = gyp_arch

  if c.BUILD_CONFIG in ['Coverage', 'Release']:
    # The 'Coverage' target is not explicitly used by Chrome, but by some other
    # projects in the Chrome ecosystem (ie: Syzygy).
    static_library(c, final=False)
  elif c.BUILD_CONFIG == 'Debug':
    shared_library(c, final=False)
  else:  # pragma: no cover
    raise BadConf('Unknown build config "%s"' % c.BUILD_CONFIG)

@config_ctx()
def gn(c):
  c.project_generator.tool = 'gn'

@config_ctx(group='builder')
def ninja(c):
  if c.TARGET_PLATFORM == 'ios':
    c.gyp_env.GYP_GENERATORS.add('ninja')

  c.compile_py.build_tool = 'ninja'

  out_path = 'out'
  if c.TARGET_CROS_BOARD:
    out_path += '_%s' % (c.TARGET_CROS_BOARD,)
  c.build_dir = Path('[CHECKOUT]', out_path)

@config_ctx(group='builder')
def msvs(c):
  if c.HOST_PLATFORM != 'win':
    raise BadConf('can not use msvs on "%s"' % c.HOST_PLATFORM)
  # If compile.py is invoking devenv it needs to refer to a solution file.
  # For chrome this defaults to ['CHECKOUT']/build/all.sln.
  c.compile_py.solution = Path('[CHECKOUT]', 'build', 'all.sln')
  c.gyp_env.GYP_GENERATORS.add('msvs')
  c.compile_py.build_tool = 'vs'
  c.build_dir = Path('[CHECKOUT]', 'build')

@config_ctx()
def msvs2010(c):
  c.gyp_env.GYP_MSVS_VERSION = '2010'

@config_ctx()
def msvs2012(c):
  c.gyp_env.GYP_MSVS_VERSION = '2012'

@config_ctx()
def msvs2013(c):
  c.gyp_env.GYP_MSVS_VERSION = '2013'

@config_ctx(group='builder')
def xcode(c):
  if c.HOST_PLATFORM != 'mac':
    raise BadConf('can not use xcodebuild on "%s"' % c.HOST_PLATFORM)
  c.gyp_env.GYP_GENERATORS.add('xcode')

def _clang_common(c):
  c.compile_py.compiler = 'clang'
  c.gyp_env.GYP_DEFINES['clang'] = 1

@config_ctx(group='compiler')
def clang(c):
  _clang_common(c)

@config_ctx(group='compiler')
def jsonclang(c):
  c.compile_py.compiler = 'jsonclang'
  c.gyp_env.GYP_DEFINES['clang'] = 1

@config_ctx(group='compiler')
def default_compiler(c):
  if c.TARGET_PLATFORM in ('mac', 'ios'):
    _clang_common(c)

@config_ctx(deps=['compiler', 'builder'], group='distributor')
def goma(c):
  if c.compile_py.build_tool == 'vs':  # pragma: no cover
    raise BadConf('goma doesn\'t work with msvs')

  # TODO(iannucci): support clang and jsonclang
  if not c.compile_py.compiler:
    c.compile_py.compiler = 'goma'
  elif c.compile_py.compiler == 'clang':
    c.compile_py.compiler = 'goma-clang'
  else:  # pragma: no cover
    raise BadConf('goma config dosen\'t understand %s' % c.compile_py.compiler)

  c.gyp_env.GYP_DEFINES['use_goma'] = 1

  goma_dir = Path('[BUILD]', 'goma')
  c.gyp_env.GYP_DEFINES['gomadir'] = goma_dir
  c.compile_py.goma_dir = goma_dir

  if c.TARGET_PLATFORM == 'win':
    fastbuild(c)
    pch(c, invert=True)

@config_ctx()
def pch(c, invert=False):
  if c.TARGET_PLATFORM == 'win':
    c.gyp_env.GYP_DEFINES['chromium_win_pch'] = int(not invert)

@config_ctx()
def dcheck(c, invert=False):
  c.gyp_env.GYP_DEFINES['dcheck_always_on'] = int(not invert)

@config_ctx()
def fastbuild(c, invert=False):
  c.gyp_env.GYP_DEFINES['fastbuild'] = int(not invert)

@config_ctx(group='link_type')
def shared_library(c):
  c.gyp_env.GYP_DEFINES['component'] = 'shared_library'

@config_ctx(group='link_type')
def static_library(c):
  c.gyp_env.GYP_DEFINES['component'] = 'static_library'

@config_ctx()
def ffmpeg_branding(c, branding=None):
  if branding:
    c.gyp_env.GYP_DEFINES['ffmpeg_branding'] = branding

@config_ctx()
def proprietary_codecs(c, invert=False):
  c.gyp_env.GYP_DEFINES['proprietary_codecs'] = int(not invert)

@config_ctx()
def chromeos(c):
  c.gyp_env.GYP_DEFINES['chromeos'] = 1
  ffmpeg_branding(c, branding='ChromeOS')
  proprietary_codecs(c)

@config_ctx()
def ozone(c):
  c.gyp_env.GYP_DEFINES['use_ozone'] = 1

@config_ctx()
def oilpan(c):
  c.gyp_env.GYP_DEFINES['enable_oilpan'] = 1

@config_ctx(includes=['static_library'])
def official(c):
  c.gyp_env.GYP_DEFINES['branding'] = 'Chrome'
  c.gyp_env.GYP_DEFINES['buildtype'] = 'Official'
  c.compile_py.clobber = True
  c.compile_py.mode = 'official'

@config_ctx(deps=['compiler'])
def asan(c):
  if 'clang' not in c.compile_py.compiler:  # pragma: no cover
    raise BadConf('asan requires clang')
  c.runtests.lsan_suppressions_file = Path('[CHECKOUT]', 'tools', 'lsan',
                                           'suppressions.txt')
  if c.TARGET_PLATFORM == 'linux':
    c.gyp_env.GYP_DEFINES['use_allocator'] = 'none'

  c.gyp_env.GYP_DEFINES['asan'] = 1
  c.gyp_env.GYP_DEFINES['lsan'] = 1

@config_ctx()
def no_lsan(c):
  c.gyp_env.GYP_DEFINES['lsan'] = 0

@config_ctx(deps=['compiler'])
def msan(c):
  if 'clang' not in c.compile_py.compiler:  # pragma: no cover
    raise BadConf('msan requires clang')
  c.gyp_env.GYP_DEFINES['msan'] = 1

@config_ctx()
def instrumented_libraries(c):
  c.gyp_env.GYP_DEFINES['use_instrumented_libraries'] = 1
  c.gyp_env.GYP_DEFINES['instrumented_libraries_jobs'] = 10

@config_ctx(group='memory_tool')
def memcheck(c):
  _memory_tool(c, 'memcheck')
  c.gyp_env.GYP_DEFINES['build_for_tool'] = 'memcheck'

@config_ctx(deps=['compiler'], group='memory_tool')
def tsan2(c):
  if 'clang' not in c.compile_py.compiler:  # pragma: no cover
    raise BadConf('tsan2 requires clang')
  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['tsan'] = 1
  gyp_defs['use_allocator'] = 'none'
  gyp_defs['use_aura'] = 1
  gyp_defs['release_extra_cflags'] = '-gline-tables-only'
  gyp_defs['disable_nacl'] = 1

@config_ctx(deps=['compiler'], group='memory_tool')
def syzyasan(c):
  if c.gyp_env.GYP_DEFINES['component'] != 'static_library':  # pragma: no cover
    raise BadConf('SyzyASan requires component=static_library')
  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['syzyasan'] = 1
  gyp_defs['win_z7'] = 1
  gyp_defs['chromium_win_pch'] = 0
  c.gyp_env.GYP_USE_SEPARATE_MSPDBSRV = 1

@config_ctx(group='memory_tool')
def drmemory_full(c):
  _memory_tool(c, 'drmemory_full')
  c.gyp_env.GYP_DEFINES['build_for_tool'] = 'drmemory'

@config_ctx(group='memory_tool')
def drmemory_light(c):
  _memory_tool(c, 'drmemory_light')
  c.gyp_env.GYP_DEFINES['build_for_tool'] = 'drmemory'

def _memory_tool(c, tool):
  if tool not in MEMORY_TOOLS:  # pragma: no cover
    raise BadConf('"%s" is not a supported memory tool, the supported ones '
                  'are: %s' % (tool, ','.join(MEMORY_TOOLS)))
  c.runtests.memory_tool = tool

@config_ctx()
def trybot_flavor(c):
  fastbuild(c, optional=True)
  dcheck(c, optional=True)

@config_ctx()
def gn_component_build(c):
  c.gn_args.append('is_component_build=true')

#### 'Full' configurations
@config_ctx(includes=['ninja', 'default_compiler'])
def chromium_no_goma(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'default_compiler', 'goma'])
def chromium(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma', 'asan'])
def chromium_asan(c):
  c.runtests.test_args.append('--test-launcher-batch-limit=1')
  c.runtests.test_args.append('--test-launcher-print-test-stdio=always')

@config_ctx(includes=['ninja', 'clang', 'goma', 'msan'])
def chromium_msan(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma', 'syzyasan'])
def chromium_syzyasan(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma', 'tsan2'])
def chromium_tsan2(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'default_compiler', 'goma', 'chromeos'])
def chromium_chromeos(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma', 'chromeos', 'asan'])
def chromium_chromeos_asan(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma', 'chromeos'])
def chromium_chromeos_clang(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['chromium_chromeos', 'ozone'])
def chromium_chromeos_ozone(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['ninja', 'clang', 'goma'])
def chromium_clang(c):
  c.compile_py.default_targets = ['All', 'chromium_builder_tests']

@config_ctx(includes=['xcode', 'static_library'])
def chromium_xcode(c):
  c.compile_py.build_tool = 'xcode'
  c.compile_py.default_targets = ['All']
  c.compile_py.xcode_project = Path('[CHECKOUT]', 'build', 'all.xcodeproj')

@config_ctx()
def chrome_internal(c):
  # For internal Chrome builds, add this flag to our 'cros' wrapper.
  c.cros_sdk_args.append('--internal')

@config_ctx(includes=['static_library'])
def ios(c):
  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['OS'] = c.TARGET_PLATFORM
  gyp_defs['chromium_ios_signing'] = 0

  if c.TARGET_BITS == 64:
    gyp_defs['target_subarch'] = 'both'

  # Do not pass target_arch explicitly, this is the current practice on iOS.
  # TODO(phajdan.jr): Clean this up and pass target_arch explicitly.
  del gyp_defs['target_arch']

  c.gyp_env.GYP_GENERATOR_FLAGS['xcode_project_version'] = '3.2'

@config_ctx(includes=['ios'])
def chromium_ios_device(c):
  c.compile_py.build_tool = 'xcode'
  c.compile_py.default_targets = ['All']
  c.compile_py.xcode_sdk = 'iphoneos7.1'

@config_ctx(includes=['ios', 'ninja'])
def chromium_ios_ninja(c):
  c.build_config_fs += '-iphoneos'
  c.compile_py.default_targets = ['All']

  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['clang_xcode'] = 0

@config_ctx(includes=['ios'])
def chromium_ios_simulator(c):
  c.compile_py.build_tool = 'xcode'
  c.compile_py.default_targets = ['All']
  c.compile_py.xcode_sdk = 'iphonesimulator7.1'

@config_ctx(includes=['chromium', 'official'])
def chromium_official(c):
  # TODO(phajdan.jr): Unify compile targets used by official builders.
  if c.TARGET_PLATFORM == 'win':
    c.compile_py.default_targets = ['chrome_official_builder']
  elif c.TARGET_PLATFORM in ['linux', 'mac']:
    c.compile_py.default_targets = []

@config_ctx(includes=['chromium'])
def blink(c):
  c.compile_py.default_targets = ['blink_tests']

@config_ctx(includes=['chromium_clang'])
def blink_clang(c):
  c.compile_py.default_targets = ['blink_tests']

@config_ctx()
def blink_logging_on(c, invert=False):
  c.gyp_env.GYP_DEFINES['blink_logging_always_on'] = int(not invert)

@config_ctx(includes=['ninja', 'static_library', 'default_compiler', 'goma'])
def android(c):
  _android_common(c)

@config_ctx(includes=['ninja', 'static_library', 'clang', 'goma'])
def android_clang(c):
  _android_common(c)

def _android_common(c):
  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['fastbuild'] = 1
  gyp_defs['OS'] = 'android'

@config_ctx(includes=['ninja', 'shared_library', 'jsonclang'])
def codesearch(c):
  gyp_defs = c.gyp_env.GYP_DEFINES
  gyp_defs['fastbuild'] = 1

@config_ctx(includes=['ninja', 'static_library'])
def chrome_pgo_base(c):
  c.gyp_env.GYP_DEFINES['buildtype'] = 'Official'
  c.gyp_env.GYP_DEFINES['optimize'] = 'max'
  c.gyp_env.GYP_DEFINES['use_goma'] = 0
  fastbuild(c, invert=True)
  c.compile_py.default_targets = ['chrome']

#### 'Full' configurations
@config_ctx(includes=['chrome_pgo_base'])
def chrome_pgo_instrument(c):
  c.gyp_env.GYP_DEFINES['chrome_pgo_phase'] = 1

@config_ctx(includes=['chrome_pgo_base'])
def chrome_pgo_optimize(c):
  c.gyp_env.GYP_DEFINES['chrome_pgo_phase'] = 2

@config_ctx()
def v8_optimize_medium(c):
  c.gyp_env.GYP_DEFINES['v8_optimized_debug'] = 1

@config_ctx()
def chromium_perf(c):
  c.compile_py.clobber = False

