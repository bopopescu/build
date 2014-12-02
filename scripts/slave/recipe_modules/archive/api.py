# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from slave import recipe_api

class ArchiveApi(recipe_api.RecipeApi):
  """Chromium specific module for zipping, uploading and downloading build
  artifacts implemented as a wrapper around zip_build.py script.

  If you need to upload or download build artifacts (or any other files) for
  something other than Chromium flavor, consider using 'zip' + 'gsutil' or
  'isolate' modules instead.
  """

  def zip_and_upload_build(
      self, step_name, target, build_url=None, src_dir=None,
      build_revision=None, cros_board=None, package_dsym_files=False,
      exclude_files=None, **kwargs):
    """Returns a step invoking zip_build.py to zip up a Chromium build.
       If build_url is specified, also uploads the build."""
    args = ['--target', target]
    if build_url:
      args.extend(['--build-url', build_url])
    if build_revision:
      args.extend(['--build_revision', build_revision])
    elif src_dir:
      args.extend(['--src-dir', src_dir])
    if cros_board:
      args.extend(['--cros-board', cros_board])
    if package_dsym_files:
      args.append('--package-dsym-files')
    if exclude_files:
      args.extend(['--exclude-files', exclude_files])
    args.extend(self.m.json.property_args())
    kwargs['allow_subannotations'] = True
    self.m.python(
      step_name,
      self.m.path['build'].join('scripts', 'slave', 'zip_build.py'),
      args,
      **kwargs
    )

  def clusterfuzz_archive(
      self, step_name, target, gs_bucket=None, cf_archive_name=None,
      revision_dir=None, **kwargs):
    """Returns a step invoking cf_archive_build.py to zip up a Chromium build
       and upload to clusterfuzz."""
    args = ['--target', target]
    if gs_bucket:
      args.extend(['--gs_bucket', gs_bucket])
    if cf_archive_name:
      args.extend(['--cf_archive_name', cf_archive_name])
    if revision_dir:
      args.extend(['--revision_dir', revision_dir])
    args.extend(['--gs_acl', 'public-read'])
    self.m.python(
      step_name,
      self.m.path['build'].join(
          'scripts', 'slave', 'chromium', 'cf_archive_build.py'),
      args,
      **kwargs
    )

  def download_and_unzip_build(
      self, step_name, target, build_url, src_dir=None,
      build_revision=None, build_archive_url=None, **kwargs):
    """Returns a step invoking extract_build.py to download and unzip
       a Chromium build."""
    args = ['--target', target]
    if build_archive_url:
      args.extend(['--build-archive-url', build_archive_url])
    else:
      args.extend(['--build-url', build_url])
      if build_revision:
        args.extend(['--build_revision', build_revision])
      elif src_dir:
        args.extend(['--src-dir', src_dir])
    args.extend(self.m.json.property_args())
    self.m.python(
      step_name,
      self.m.path['build'].join('scripts', 'slave', 'extract_build.py'),
      args,
      **kwargs
    )

  def _legacy_platform_name(self):
    """Replicates the behavior of PlatformName() in chromium_utils.py."""
    if self.m.platform.is_win:
      return 'win32'
    return self.m.platform.name

  def _legacy_url(self, is_download, gs_bucket_name, extra_url_components):
    """Computes a build_url suitable for uploading a zipped Chromium
    build to Google Storage.

    The reason this is named 'legacy' is that there are a large number
    of dependencies on the exact form of this URL. The combination of
    zip_build.py, extract_build.py, slave_utils.py, and runtest.py
    require that:

    * The platform name be exactly one of 'win32', 'mac', or 'linux'
    * The upload URL only name the directory on GS into which the
      build goes (zip_build.py computes the name of the file)
    * The download URL contain the unversioned name of the zip archive
    * The revision on the builder and tester machines be exactly the
      same

    There were too many dependencies to tease apart initially, so this
    function simply emulates the form of the URL computed by the
    underlying scripts.

    extra_url_components, if specified, should be a string without a
    trailing '/' which is inserted in the middle of the URL.

    The builder_name, or parent_buildername, is always automatically
    inserted into the URL."""

    result = ('gs://' + gs_bucket_name)
    if extra_url_components:
      result += ('/' + extra_url_components)
    if is_download:
      result += ('/' + self.m.properties['parent_buildername'] + '/' +
                 'full-build-' + self._legacy_platform_name() +
                 '.zip')
    else:
      result += '/' + self.m.properties['buildername']
    return result

  def legacy_upload_url(self, gs_bucket_name, extra_url_components=None):
    """Returns a url suitable for uploading a Chromium build to Google
    Storage.

    extra_url_components, if specified, should be a string without a
    trailing '/' which is inserted in the middle of the URL.

    The builder_name, or parent_buildername, is always automatically
    inserted into the URL."""
    return self._legacy_url(False, gs_bucket_name, extra_url_components)

  def legacy_download_url(self, gs_bucket_name, extra_url_components=None):
    """Returns a url suitable for downloading a Chromium build from
    Google Storage.

    extra_url_components, if specified, should be a string without a
    trailing '/' which is inserted in the middle of the URL.

    The builder_name, or parent_buildername, is always automatically
    inserted into the URL."""
    return self._legacy_url(True, gs_bucket_name, extra_url_components)

  def archive_dependencies(
      self, step_name, target, master, builder, build, **kwargs):
    """Returns a step invoking archive_dependencies.py to zip up and upload
       build dependency information for the build."""
    try:
      script = self.m.path['build'].join('scripts',
                                         'slave',
                                         'archive_dependencies.py')
      args = []
      args.extend(['--src-dir', self.m.path['checkout']])
      args.extend(['--target', target])
      args.extend(['--master', master])
      args.extend(['--builder', builder])
      args.extend(['--build', build])
      self.m.python(step_name, script, args, **kwargs)
    except self.m.step.StepFailure:
      pass
