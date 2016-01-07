# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os


def get_orochi_xdg_dir(env_var, fallback):
    """
    Try to return the orochi folder below the XDG directory defined with the
    chosen env variable.

    Examples include ``XDG_CONFIG_HOME`` or ``XDG_CACHE_HOME``.

    If the environment variable is not available, fall back to
    ``~/<fallback>/orochi``, where ``<fallback>`` is specified as the second
    parameter.

    If the directory does not yet exist, it will be created before returning
    the path to it.

    """

    xdg_dir = os.environ.get(env_var)
    if not xdg_dir:
        xdg_dir = os.path.join(os.path.expanduser('~'), fallback)
    orochi_dir = os.path.join(xdg_dir, 'orochi')
    if not os.path.isdir(orochi_dir):
        os.makedirs(orochi_dir)
    return orochi_dir
