# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals


class CommandError(RuntimeError):
    """Raised when a command could not be passed on to the player, or if an
    error occured while executing it."""


class TerminatedError(RuntimeError):
    """An exception that is raised when interaction with the player is
    attempted even if the background thread is already dead."""


class InitializationError(RuntimeError):
    """Raised when initialization of player failed."""
