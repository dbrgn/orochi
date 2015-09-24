# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

from orochi import colors


def test_bold():
    """Test whether the bold() function works properly."""
    assert colors.bold('spam') == colors.ANSI_BOLD + 'spam' + colors.ANSI_NORMAL
    assert colors.bold('spam') == '\033[1mspam\033[22m'


def test_title():
    """Test whether title() generates the correct strings."""
    assert colors.title('spam') == colors.ANSI_WINDOW_NAME_START + 'spam' + \
                                   colors.ANSI_WINDOW_NAME_END
    assert colors.title('spam') == '\033]2;spam\007'
