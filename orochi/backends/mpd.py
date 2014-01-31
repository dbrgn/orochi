# -*- coding: utf-8 -*-
"""
This module implements an MPD player. It uses the python-mpd2 library to talk
to the MPD server.
"""
from __future__ import print_function, division, absolute_import, unicode_literals

import functools

import mpd

from .. import errors
from .interface import Player


def catch_command_error(msg):
    """This catches any ``mpd.CommandError`` and converts it into a custom
    ``CommandError``."""
    def real_decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                fn(*args, **kwargs)
            except mpd.CommandError as e:
                raise errors.CommandError('{0} Details: {1!s}'.format(msg, e))
        return wrapper
    return real_decorator


class MPDPlayer(Player):

    def __init__(self, timeout=15, *args, **kwargs):
        """Create a new player process.

        :param timeout: The number of seconds to wait for a command to finish. Default: 15.
        :type timeout: int

        """
        # Initialize client
        self.client = mpd.MPDClient()
        # Set timeouts
        self.client.timeout = timeout
        self.client.idletimeout = None
        # Connect to server
        self._connect()
        # Clear current playlist
        self.client.clear()

    def _connect(self, host='127.0.0.1', port=6600):
        """Connect to the specified MPD server.

        :param host: The hostname or IP of the MPD server.
        :type host: string
        :param port: The port of the MPD server.
        :type port: int

        """
        self.client.connect(host, port)

    @catch_command_error('Could not load & play song.')
    def load(self, path):
        """Load a file and play it.

        :param path: The path (url or filepath) to the file which should be played.
        :type path: string

        """
        # To prevent going back to the previous song (8tracks disallows it),
        # the playlist is cleared each time before loading the new track.
        try:
            self.client.clear()
        except mpd.CommandError as e:
            raise errors.CommandError('Could not clear playlist: {!s}'.format(e))
        self.client.add(path)
        self.client.play()

    @catch_command_error('Could not play or pause song.')
    def playpause(self):
        """Pause or resume the playback of a song."""
        self.client.pause()

    @catch_command_error('Could not play stop playback.')
    def stop(self):
        """Stop playback."""
        self.client.stop()

    @catch_command_error('Could not set volume.')
    def volume(self, amount):
        """Set the playback volume to ``amount`` percent.

        :param amount: The volume level, must be a number between 0 and 100.
        :type amount: int
        :raises: ValueError

        """
        try:
            amount = int(amount)
            assert 0 <= amount <= 100
        except (ValueError, AssertionError):
            raise ValueError('``amount`` must be an integer between 0 and 100.')
        self.client.setvol(amount)

    def terminate(self):
        """Terminate the instance."""
        self.client.close()
