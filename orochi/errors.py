# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals


class TerminatedError(RuntimeError):
    """An exception that is raised when interaction with the player is
    attempted even if the background thread is already dead."""
    pass


class InitializationError(RuntimeError):
    """Raised when initialization of player failed."""
    pass
