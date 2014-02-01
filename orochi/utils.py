# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os


def get_xdg_config_home():
    """Return the orochi config dir according to the XDG specification."""
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
    if not xdg_config_home:
        xdg_config_home = os.path.join(os.path.expanduser('~'), '.config')
    configdir = os.path.join(xdg_config_home, 'orochi')
    if not os.path.isdir(configdir):
        os.makedirs(configdir)
    return configdir
