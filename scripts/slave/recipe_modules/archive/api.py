# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from slave import recipe_api


# Regular expression to identify a Git hash.
GIT_COMMIT_HASH_RE = re.compile(r'[a-zA-Z0-9]{40}')
# The Google Storage metadata key for the full commit position.
GS_COMMIT_POSITION_KEY = 'Cr-Commit-Position'
# The Google Storage metadata key for the commit position number.
GS_COMMIT_POSITION_NUMBER_KEY = 'Cr-Commit-Position-Number'
# The Google Storage metadata key for the Git commit hash.
GS_GIT_COMMIT_KEY = 'Cr-Git-Commit'


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
      infra_step=True,
      **kwargs
    )

  def _file_exclusions(self):
    # TODO(machenbach): Extract to static constant toplevel sets.
    """Returns a platform-dependent list of excluded files for archiving."""
    all_platforms = ['.landmines', 'obj', 'gen', '.ninja_deps', '.ninja_log']
    # Skip files that the testers don't care about. Mostly directories.
    if self.m.platform.is_win:
      # Remove obj or lib dir entries
      return all_platforms + [
        'cfinstaller_archive', 'lib', 'installer_archive']
    if self.m.platform.is_mac:
      return all_platforms + [
        # We don't need the arm bits v8 builds.
        'd8_arm', 'v8_shell_arm',
        # pdfsqueeze is a build helper, no need to copy it to testers.
        'pdfsqueeze',
        # We copy the framework into the app bundle, we don't need the second
        # copy outside the app.
        # TODO(mark): Since r28431, the copy in the build directory is actually
        # used by tests.  Putting two copies in the .zip isn't great, so maybe
        # we can find another workaround.
        # 'Chromium Framework.framework',
        # 'Google Chrome Framework.framework',
        # We copy the Helper into the app bundle, we don't need the second
        # copy outside the app.
        'Chromium Helper.app',
        'Google Chrome Helper.app',
        'App Shim Socket',
        '.deps', 'obj.host', 'obj.target', 'lib'
      ]
    if self.m.platform.is_linux:
      return all_platforms + [
        # Intermediate build directories (full of .o, .d, etc.).
        'appcache', 'glue', 'lib.host', 'obj.host',
        'obj.target', 'src', '.deps',
        # Scons build cruft
        '.sconsign.dblite',
        # Build helper, not needed on testers
        'mksnapshot',
      ]

    raise NotImplementedError('Platform is not supported.')  # pragma: no cover

  def _cf_should_package_file(self, filename):
    """Returns true if the file should be a part of the resulting archive."""
    if self.m.platform.is_mac:
      file_filter = r'^.+\.(a)$'
    elif self.m.platform.is_linux:
      file_filter = r'^.+\.(o|a|d)$'
    elif self.m.platform.is_win:
      file_filter = r'^.+\.(obj|lib|pch|exp)$'
    else:  # pragma: no cover
      raise NotImplementedError('Platform is not supported.')
    if re.match(file_filter, filename):
      return False

    # Skip files that we don't care about. Mostly directories.
    # TODO(machenbach): This should refer to a static set.
    things_to_skip = self._file_exclusions()

    if filename in things_to_skip:
      return False

    return True

  def _get_commit_position(self, update_properties, primary_project):
    """Returns the commit position of the project (or the specified primary
    project).
    """
    if primary_project:
      key = 'got_%s_revision_cp' % primary_project
    else:
      key = 'got_revision_cp'
    return update_properties[key]

  def _get_git_commit(self, update_properties, primary_project):
    """Returns: (str/None) the git commit hash for a given project.

    Attempts to identify the git commit hash for a given project. If
    'primary_project' is None, or if there is no git commit hash for the
    specified primary project, the checkout-wide commit hash will be used.

    If none of the candidate configurations are present, the value None will be
    returned.
    """
    if primary_project:
      commit = update_properties.get('got_%s_revision_git' % primary_project)
      if commit:
        return commit
      commit = update_properties.get('got_%s_revision' % primary_project)
      if commit and GIT_COMMIT_HASH_RE.match(commit):
        return commit
    
    commit = update_properties.get('got_revision_git')
    if commit:
      return commit
    commit = update_properties.get('got_revision')
    if commit and GIT_COMMIT_HASH_RE.match(commit):
      return commit
    return None

  def _get_comparable_upload_path_for_sort_key(self, branch, number):
    """Returns a sortable string corresponding to the commit position."""
    if branch and branch != 'refs/heads/master':
      branch = branch.replace('/', '_')
      return '%s-%s' % (branch, number)
    return str(number)

  def clusterfuzz_archive(
      self, build_dir, update_properties, gs_bucket,
      archive_prefix, archive_subdir_suffix='', gs_acl=None,
      revision_dir=None, primary_project=None, **kwargs):
    # TODO(machenbach): Merge revision_dir and primary_project. The
    # revision_dir is only used for building the archive name while the
    # primary_project is authoritative for the commit position.
    """Archives and uploads a build to google storage.

    The build is filtered by a list of file exclusions and then zipped. It is
    uploaded to google storage with some metadata about the commit position
    and revision attached. The zip file follows the naming pattern used by
    clusterfuzz. The file pattern is:
    <archive name>-<platform>-<target><optional component>-<sort-key>.zip

    Example: cool-project-linux-release-refs_heads_b1-12345.zip
    The archive name is "cool-project" and there's no component build. The
    commit is on a branch called b1 at commit position number 12345.

    Example: cool-project-mac-debug-x10-component-234.zip
    The archive name is "cool-project" and the component's name is "x10". The
    component is checked out in branch master with commit position number 234.

    Args:
      build_dir: The absolute path to the build output directory, e.g.
                 [slave-build]/src/out/Release
      update_properties: The properties from the bot_update step (containing
                         commit information)
      gs_bucket: Name of the google storage bucket to upload to
      archive_prefix: Prefix of the archive zip file
      archive_subdir_suffix: Optional suffix to the google storage subdirectory
                             name that contains the archive files
      gs_acl: ACL used for the file on google storage
      revision_dir: Optional component name if the main revision for this
                    archive is a component revision
      primary_project: Optional project name for specifying the revision of the
                       checkout
    """
    target = self.m.path.split(build_dir)[-1]
    commit_position = self._get_commit_position(
        update_properties, primary_project)
    cp_branch, cp_number = self.m.commit_position.parse(commit_position)
    build_git_commit = self._get_git_commit(update_properties, primary_project)

    staging_dir = self.m.path['slave_build'].join('chrome_staging')

    # Build the list of files to archive.
    zip_file_list = [f for f in self.m.path.listdir('build_dir', build_dir)
                     if self._cf_should_package_file(f)]

    pieces = [self.m.platform.name, target.lower()]
    if archive_subdir_suffix:
      pieces.append(archive_subdir_suffix)
    subdir = '-'.join(pieces)

    # Components like v8 get a <name>-v8-component-<revision> infix.
    component = ''
    if revision_dir:
      component = '-%s-component' % revision_dir

    sortkey_path = self._get_comparable_upload_path_for_sort_key(
        cp_branch, cp_number)
    zip_file_name = '%s-%s-%s%s-%s.zip' % (archive_prefix,
                                           self.m.platform.name,
                                           target.lower(),
                                           component,
                                           sortkey_path)

    zip_file = staging_dir.join(zip_file_name)
    package = self.m.zip.make_package(build_dir, zip_file)
    for f in zip_file_list:
      package.add_file(package.root.join(f))
    package.zip('zipping')

    # TODO(machenbach): This feature has not migrated yet.
    # Report the size of the zip file to help catch when it gets too big.
    # zip_size = os.stat(zip_file)[stat.ST_SIZE]
    # print 'Zip file is %ld bytes' % zip_size

    gs_metadata = {
      GS_COMMIT_POSITION_NUMBER_KEY: cp_number,
    }
    if commit_position:
      gs_metadata[GS_COMMIT_POSITION_KEY] = commit_position
    if build_git_commit:
      gs_metadata[GS_GIT_COMMIT_KEY] = build_git_commit

    gs_args = []
    if gs_acl:
      gs_args.extend(['-a', gs_acl])
    self.m.gsutil.upload(
        zip_file,
        gs_bucket,
        "/".join([subdir, zip_file_name]),
        args=gs_args,
        metadata=gs_metadata,
    )
    self.m.file.remove(zip_file_name, zip_file)

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
      infra_step=True,
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
      self.m.python(step_name, script, args, infra_step=True, **kwargs)
    except self.m.step.StepFailure:
      pass
