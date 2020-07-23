#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Reads main.cfg and makes exports for buildbot."""

import sys

def main(_argv):

  localDict = {'__file__': 'main.cfg'}

  with open(localDict['__file__'], 'r') as f:
    exec f in localDict

  localDict['WriteHTMLFragments']()

if __name__ == '__main__':
  sys.exit(main(sys.argv))
