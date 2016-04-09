# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import sys
import tempfile
import unittest


LOCATION = os.path.dirname(os.path.abspath(__file__))


# This branched off commit 2 below.
PATCH1 = """
Index: test2
index b5d8dd0..257cc56 100644
--- a/test2
+++ b/test2
@@ -1 +1 @@
-2_2
\ No newline at end of file
+foo
"""

# This branched off commit 4 below.
PATCH2 = """
Index: test1
index 65824f6..7601807 100644
--- a/test1
+++ b/test1
@@ -1 +1 @@
-1_4
\ No newline at end of file
+baz
Index: test3
index dca23b6..5716ca5 100644
--- a/test3
+++ b/test3
@@ -1 +1 @@
-3_4
\ No newline at end of file
+bar
"""

# This branched off commit 2 below and adds a new file.
PATCH3 = """
Index: baz
new file mode 100644
index 0000000..7601807
--- /dev/null
+++ b/baz
@@ -0,0 +1 @@
+baz
Index: test2
index b5d8dd0..257cc56 100644
--- a/test2
+++ b/test2
@@ -1 +1 @@
-2_2
\ No newline at end of file
+foo
"""

# This branched off commit 2 below and adds a new file. The diff considers
# the new file as a copy of "test2".
PATCH4 = """
Index: baz
new file mode 100644
copy from test2
copy to baz
index b5d8dd0..7601807
--- /dev/null
+++ b/baz
@@ -0,0 +1 @@
+baz
"""

# Same as above with rename.
PATCH5 = """
Index: baz
new file mode 100644
rename from test2
rename to baz
index b5d8dd0..7601807
--- /dev/null
+++ b/baz
@@ -0,0 +1 @@
+baz
"""


class PatchBaseTest(unittest.TestCase):
  @classmethod
  def git(cls, *args):
    return subprocess.check_output(
      ['git'] + list(args),
      cwd=cls.repo
    ).strip()

  @classmethod
  def write_file(cls, name, content):
    with open(os.path.join(cls.repo, name), 'w') as f:
      f.write(content)

  @classmethod
  def setUpClass(cls):
    cls.repo = tempfile.mkdtemp()
    cls.git('init')
    cls.write_file('test1', '1_1')
    cls.write_file('test2', '2_1')
    cls.git('add', 'test1', 'test2')
    cls.git('commit', '-m', 'Commit1')

    cls.write_file('test1', '1_2')
    cls.write_file('test2', '2_2')
    cls.git('commit', '-am', 'Commit2')

    cls.write_file('test1', '1_3')
    cls.write_file('test2', '2_3')
    cls.git('commit', '-am', 'Commit3')

    cls.write_file('test1', '1_4')
    cls.write_file('test2', '2_4')
    cls.write_file('test3', '3_4')
    cls.git('add', 'test3')
    cls.git('commit', '-am', 'Commit4')

    cls.write_file('test1', '1_5')
    cls.write_file('test2', '2_5')
    cls.git('commit', '-am', 'Commit5')

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.repo)

  def setUp(self):
    self.workdir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.workdir)

  def calculate_patch_base(self, patch):
    patch_file = os.path.join(self.workdir, 'patch')
    result_file = os.path.join(self.workdir, 'result')
    with open(patch_file, 'w') as f:
      f.write(patch)
    subprocess.check_call(
      [
        sys.executable, '-u', 'calculate_patch_base.py',
        patch_file, self.repo, result_file,
      ],
      cwd=LOCATION,
    )
    with open(result_file) as f:
      result = f.read().strip()
      return self.git('log', '-n1', '--format=%s', result)

  def testMatch(self):
    commit_title = self.calculate_patch_base(PATCH1)
    self.assertEquals('Commit2', commit_title)

  def testMatchTwoFiles(self):
    commit_title = self.calculate_patch_base(PATCH2)
    self.assertEquals('Commit4', commit_title)

  def testFileAdded(self):
    commit_title = self.calculate_patch_base(PATCH3)
    self.assertEquals('Commit2', commit_title)

  def testFileCopied(self):
    commit_title = self.calculate_patch_base(PATCH4)
    self.assertEquals('Commit2', commit_title)

  def testFileRename(self):
    commit_title = self.calculate_patch_base(PATCH5)
    self.assertEquals('Commit2', commit_title)