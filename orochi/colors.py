# -*- coding: utf-8 -*-
"""
This module contains constants with ANSI escape codes as well as helper
functions to use them.
"""
from __future__ import print_function, division, absolute_import, unicode_literals


# ANSI escape sequences

ANSI_BOLD = '\033[1m'
ANSI_NORMAL = '\033[22m'
ANSI_WINDOW_NAME_START = '\033]2;'
ANSI_WINDOW_NAME_END = '\007'


# Helper functions

def bold(text):
    return ''.join([ANSI_BOLD, text, ANSI_NORMAL])


def title(text):
    return ''.join([ANSI_WINDOW_NAME_START, text, ANSI_WINDOW_NAME_END])
