# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from recipe_engine import recipe_api



class CTApi(recipe_api.RecipeApi):
  """Provides steps to run CT tasks."""

  CT_GS_BUCKET = 'cluster-telemetry'

  @property
  def downloads_dir(self):
    """Path to where artifacts should be downloaded from Google Storage."""
    return self.m.path['subordinate_build'].join('src', 'content', 'test', 'ct')

  def checkout_dependencies(self):
    """Checks out all repositories required for CT to run."""
    self.m.chromium.set_config('chromium')
    self.m.gclient.set_config('chromium')
    self.m.bot_update.ensure_checkout(force=True)

  def download_skps(self, page_type, subordinate_num, skps_chromium_build, dest_dir):
    """Downloads SKPs corresponding to the specified page type, subordinate and build.

    The SKPs are downloaded into subdirectories in the dest_dir.

    Args:
      api: RecipeApi instance.
      page_type: str. The CT page type. Eg: 1k, 10k.
      subordinate_num: int. The number of the subordinate used to determine which GS
                 directory to download from. Eg: for the top 1k, subordinate1 will
                 contain SKPs from webpages 1-10, subordinate2 will contain 11-20.
      skps_chromium_build: str. The build the SKPs were captured from.
      dest_dir: path obj. The directory to download SKPs into.
    """
    skps_dir = dest_dir.join('subordinate%s' % subordinate_num)
    self.m.file.makedirs('SKPs dir', skps_dir)
    full_source = 'gs://%s/skps/%s/%s/subordinate%s' % (
        self.CT_GS_BUCKET, page_type, skps_chromium_build, subordinate_num)
    self.m.gsutil(['-m', 'rsync', '-d', '-r', full_source, skps_dir])

  def download_CT_binary(self, ct_binary_name):
    """Downloads the specified CT binary from GS into the downloads_dir."""
    binary_dest = self.downloads_dir.join(ct_binary_name)
    self.m.gsutil.download(
        name="download %s" % ct_binary_name,
        bucket=self.CT_GS_BUCKET,
        source='swarming/binaries/%s' % ct_binary_name,
        dest=binary_dest)
    # Set executable bit on the binary.
    self.m.python.inline(
        name='Set executable bit on %s' % ct_binary_name,
        program='''
import os
import stat

os.chmod('%s', os.stat('%s').st_mode | stat.S_IEXEC)
''' % (str(binary_dest), str(binary_dest))
    )

  def download_page_artifacts(self, page_type, subordinate_num):
    """Downloads all the artifacts needed to run benchmarks on a page.

    The artifacts are downloaded into subdirectories in the downloads_dir.

    Args:
      page_type: str. The CT page type. Eg: 1k, 10k.
      subordinate_num: int. The number of the subordinate used to determine which GS
                 directory to download from. Eg: for the top 1k, subordinate1 will
                 contain webpages 1-10, subordinate2 will contain 11-20.
    """
    # Download page sets.
    page_sets_dir = self.downloads_dir.join('subordinate%s' % subordinate_num, 'page_sets')
    self.m.file.makedirs('page_sets dir', page_sets_dir)
    self.m.gsutil.download(
        bucket=self.CT_GS_BUCKET,
        source='swarming/page_sets/%s/subordinate%s/*' % (page_type, subordinate_num),
        dest=page_sets_dir)

    # Download archives.
    wpr_dir = page_sets_dir.join('data')
    self.m.file.makedirs('WPR dir', wpr_dir)
    self.m.gsutil.download(
        bucket=self.CT_GS_BUCKET,
        source='swarming/webpage_archives/%s/subordinate%s/*' % (page_type,
                                                           subordinate_num),
        dest=wpr_dir)
