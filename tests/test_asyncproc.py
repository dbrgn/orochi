# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import subprocess
import sys


def test_asyncproc():
    """Test that with_timeout doesn't fail on exit."""

    code = """
import sys
from orochi.asyncproc import with_timeout

class DelFunc(object):
    def __init__(self, func, *args):
        self.func = func
        self.args = args

    def __del__(self):
        self.func(*self.args)

df = DelFunc(with_timeout, 1, lambda:1)
sys.exit()
    """

    output = subprocess.check_output([sys.executable, "-Ec", code],
                                     stderr=subprocess.STDOUT)

    assert "Exception" not in output
