# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from slave import recipe_api
from slave import recipe_util

import textwrap

class PythonApi(recipe_api.RecipeApi):
  def __call__(self, name, script, args=None, unbuffered=True, **kwargs):
    """Return a step to run a python script with arguments."""
    cmd = ['python']
    if unbuffered:
      cmd.append('-u')
    cmd.append(script)
    return self.m.step(name, cmd + list(args or []), **kwargs)

  def inline(self, name, program, add_python_log=True, **kwargs):
    """Run an inline python program as a step.

    Program is output to a temp file and run when this step executes.
    """
    program = textwrap.dedent(program)
    compile(program, '<string>', 'exec', dont_inherit=1)

    try:
      self(name, self.m.raw_io.input(program, '.py'), **kwargs)
    finally:
      result = self.m.step.active_result
      if result and add_python_log:
        result.presentation.logs['python.inline'] = program.splitlines()

    return result

  def failing_step(self, name, text):
    """Return a failng step (correctly recognized in expectations)."""
    try:
      self.inline(name,
                  'import sys; sys.exit(1)',
                  add_python_log=False,
                  step_test_data=lambda: self.m.raw_io.test_api.output(
                      text, retcode=1))
    finally:
      self.m.step.active_result.presentation.step_text = text
