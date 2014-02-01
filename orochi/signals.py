# -*- coding: utf-8 -*-
"""
A collection of signals used in Orochi.

"""
from __future__ import print_function, division, absolute_import, unicode_literals

import signal


"""The SONG_ENDED signal is raised when a song has finished playing."""
SONG_ENDED = signal.SIGUSR1

"""The REGISTER_SONG signal is raised when a song has been playing for 30 seconds."""
REGISTER_SONG = signal.SIGUSR2
