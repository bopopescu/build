# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Default flavor utils class, used for desktop builders."""


import json


class DeviceDirs(object):
  def __init__(self,
               dm_dir,
               perf_data_dir,
               resource_dir,
               images_dir,
               skp_dir,
               tmp_dir):
    self._dm_dir = dm_dir
    self._perf_data_dir = perf_data_dir
    self._resource_dir = resource_dir
    self._images_dir = images_dir
    self._skp_dir = skp_dir
    self._tmp_dir = tmp_dir

  @property
  def dm_dir(self):
    """Where DM writes."""
    return self._dm_dir

  @property
  def perf_data_dir(self):
    return self._perf_data_dir

  @property
  def resource_dir(self):
    return self._resource_dir

  @property
  def images_dir(self):
    return self._images_dir

  @property
  def skp_dir(self):
    """Holds SKP files that are consumed by RenderSKPs and BenchPictures."""
    return self._skp_dir

  @property
  def tmp_dir(self):
    return self._tmp_dir


class DefaultFlavorUtils(object):
  """Utilities to be used by build steps.

  The methods in this class define how certain high-level functions should
  work. Each build step flavor should correspond to a subclass of
  DefaultFlavorUtils which may override any of these functions as appropriate
  for that flavor.

  For example, the AndroidFlavorUtils will override the functions for
  copying files between the host and Android device, as well as the
  'step' function, so that commands may be run through ADB.
  """
  def __init__(self, skia_api, *args, **kwargs):
    self._skia_api = skia_api
    self._chrome_path = None

  def step(self, name, cmd, **kwargs):
    """Wrapper for the Step API; runs a step as appropriate for this flavor."""
    path_to_app = self._skia_api.out_dir.join(
        self._skia_api.configuration, cmd[0])
    if (self._skia_api.m.platform.is_linux and
        'x86_64' in self._skia_api.builder_name and
        not 'TSAN' in self._skia_api.builder_name):
      new_cmd = ['catchsegv', path_to_app]
    else:
      new_cmd = [path_to_app]
    new_cmd.extend(cmd[1:])
    return self._skia_api.run(self._skia_api.m.step,
                              name, cmd=new_cmd, **kwargs)

  @property
  def chrome_path(self):
    """Path to a checkout of Chrome on this machine."""
    if self._chrome_path is None:
      if self._skia_api.running_in_swarming:
        self._chrome_path = self._skia_api.subordinate_dir.join('src')
        return self._chrome_path

      toolchain_hash_file = self._skia_api.skia_dir.join(
          'infra', 'bots', 'win_toolchain_hash.json')
      if (self._skia_api.m.path.exists(toolchain_hash_file) and
          self._skia_api.builder_cfg.get('extra_config') == 'VS2015'):
        # Find the desired toolchain version.
        test_data = '''{
    "2013": "705384d88f80da637eb367e5acc6f315c0e1db2f",
    "2015": "38380d77eec9164e5818ae45e2915a6f22d60e85"
}'''
        j = self._skia_api._readfile(toolchain_hash_file,
                                     name='Read win_toolchain_hash.json',
                                     test_data=test_data).rstrip()
        hashes = json.loads(j)
        desired_vs_version = '2013'
        if 'VS2015' in self._skia_api.builder_cfg.get('extra_config', ''):
          desired_vs_version = '2015'
        desired_hash = hashes[desired_vs_version]

        # Find the actually-downloaded toolchain version.
        self._skia_api._run_once(self._skia_api.m.file.makedirs,
                       'tmp_dir',
                       self._skia_api.tmp_dir,
                       infra_step=True)
        version_file = 'WIN_TOOLCHAIN_HASH'
        actual_hash_file = self._skia_api.m.path.join(self._skia_api.tmp_dir,
                                                      version_file)
        test_expected_version = 'abc123'
        try:
          actual_hash = self._skia_api._readfile(
              actual_hash_file,
              name='Get downloaded %s' % version_file,
              test_data=test_expected_version).rstrip()
        except self._skia_api.m.step.StepFailure:
          actual_hash = None
        toolchain_dir = self._skia_api.subordinate_dir.join('win')
        toolchain_src_dir = toolchain_dir.join('src')

        # Download the toolchain if necessary.
        if actual_hash != desired_hash:
          self._skia_api.rmtree(toolchain_dir,
                                self._skia_api.running_in_swarming)
          self._skia_api.m.swarming_client.checkout(revision='')
          self._skia_api.m.swarming.check_client_version()
          isolateserver = (
              self._skia_api.m.swarming_client.path.join('isolateserver.py'))
          isolate_cache_dir = self._skia_api.m.path.join(
              self._skia_api.home_dir, '.isolate_cache')
          self._skia_api.m.python(
              'Download Win Toolchain',
              script=isolateserver,
              args=['download',
                    '-I', 'https://isolateserver.appspot.com',
                    '-s', desired_hash,
                    '-t', toolchain_dir,
                    '--cache', isolate_cache_dir])
          bootstrap_script = self._skia_api.infrabots_dir.join(
              'bootstrap_win_toolchain_json.py')
          win_toolchain_json = toolchain_src_dir.join(
              'build', 'win_toolchain.json')
          self._skia_api.m.python(
              'Bootstrap Win Toolchain',
              script=bootstrap_script,
              args=['--win_toolchain_json', win_toolchain_json,
                    '--depot_tools_parent_dir', toolchain_dir])
          self._skia_api._writefile(actual_hash_file, desired_hash)
        self._chrome_path = toolchain_src_dir
      else:
        self._chrome_path = self._skia_api.m.path.join(
            self._skia_api.home_dir, 'src')
    return self._chrome_path

  def bootstrap_win_toolchain(self):
    """Run bootstrapping script for the Windows toolchain."""
    bootstrap_script = self._skia_api.infrabots_dir.join(
        'bootstrap_win_toolchain_json.py')
    win_toolchain_json = self._skia_api.subordinate_dir.join(
        'src', 'build', 'win_toolchain.json')
    self._skia_api.m.python(
        'bootstrap win toolchain',
        script=bootstrap_script,
        args=['--win_toolchain_json', win_toolchain_json,
              '--depot_tools_parent_dir', self._skia_api.subordinate_dir])

  def compile(self, target):
    """Build the given target."""
    # The CHROME_PATH environment variable is needed for builders that use
    # toolchains downloaded by Chrome.
    env = {'CHROME_PATH': self.chrome_path}
    if self._skia_api.m.platform.is_win:
      make_cmd = ['python', 'make.py']
      if self._skia_api.running_in_swarming:
        self._skia_api._run_once(self.bootstrap_win_toolchain)
      else:
        if 'VS2015' in self._skia_api.builder_cfg.get('extra_config', ''):
          env['PATH'] = self._skia_api.m.path.pathsep.join([
              str(self._skia_api.subordinate_dir.join('win', 'depot_tools')),
              '%(PATH)s'])
          env['GYP_MSVS_VERSION'] = '2015'
    else:
      make_cmd = ['make']
    cmd = make_cmd + [target]
    self._skia_api.run(self._skia_api.m.step, 'build %s' % target, cmd=cmd,
                       env=env, cwd=self._skia_api.m.path['checkout'])

  def device_path_join(self, *args):
    """Like os.path.join(), but for paths on a connected device."""
    return self._skia_api.m.path.join(*args)

  def device_path_exists(self, path):
    """Like os.path.exists(), but for paths on a connected device."""
    return self._skia_api.m.path.exists(path, infra_step=True)  # pragma: no cover

  def copy_directory_contents_to_device(self, host_dir, device_dir):
    """Like shutil.copytree(), but for copying to a connected device."""
    # For "normal" builders who don't have an attached device, we expect
    # host_dir and device_dir to be the same.
    if str(host_dir) != str(device_dir):
      raise ValueError('For builders who do not have attached devices, copying '
                       'from host to device is undefined and only allowed if '
                       'host_path and device_path are the same (%s vs %s).' % (
                       str(host_dir), str(device_dir)))  # pragma: no cover

  def copy_directory_contents_to_host(self, device_dir, host_dir):
    """Like shutil.copytree(), but for copying from a connected device."""
    # For "normal" builders who don't have an attached device, we expect
    # host_dir and device_dir to be the same.
    if str(host_dir) != str(device_dir):
      raise ValueError('For builders who do not have attached devices, copying '
                       'from device to host is undefined and only allowed if '
                       'host_path and device_path are the same (%s vs %s).' % (
                       str(host_dir), str(device_dir)))  # pragma: no cover

  def copy_file_to_device(self, host_path, device_path):
    """Like shutil.copyfile, but for copying to a connected device."""
    # For "normal" builders who don't have an attached device, we expect
    # host_dir and device_dir to be the same.
    if str(host_path) != str(device_path):  # pragma: no cover
      raise ValueError('For builders who do not have attached devices, copying '
                       'from host to device is undefined and only allowed if '
                       'host_path and device_path are the same (%s vs %s).' % (
                       str(host_path), str(device_path)))

  def create_clean_device_dir(self, path):
    """Like shutil.rmtree() + os.makedirs(), but on a connected device."""
    self.create_clean_host_dir(path)

  def create_clean_host_dir(self, path):
    """Convenience function for creating a clean directory."""
    self._skia_api.rmtree(path, self._skia_api.running_in_swarming)
    self._skia_api.m.file.makedirs(
        self._skia_api.m.path.basename(path), path, infra_step=True)

  def install(self):
    """Run device-specific installation steps."""
    pass

  def cleanup_steps(self):
    """Run any device-specific cleanup steps."""
    pass

  def get_device_dirs(self):
    """ Set the directories which will be used by the build steps.

    These refer to paths on the same device where the test executables will
    run, for example, for Android bots these are paths on the Android device
    itself. For desktop bots, these are just local paths.
    """
    pardir = self._skia_api.m.path.pardir
    join = self._skia_api.m.path['subordinate_build'].join
    return DeviceDirs(
        dm_dir=self._skia_api.dm_dir,
        perf_data_dir=self._skia_api.perf_data_dir,
        resource_dir=self._skia_api.resource_dir,
        images_dir=join('images'),
        skp_dir=self._skia_api.local_skp_dir,
        tmp_dir=join('tmp'))

  def __repr__(self):
    return '<%s object>' % self.__class__.__name__  # pragma: no cover
