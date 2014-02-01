# -*- coding: utf-8 -*-
"""
This module implements an MPD player. It uses the python-mpd2 library to talk
to the MPD server.
"""
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import threading
import functools
import logging

import mpd

from .. import errors, signals
from .interface import Player


# Set up logging
logger = logging.getLogger('orochi')


def catch_mpd_error(msg):
    """Decorator to catch MPD exceptions and convert them into a custom
    ``CommandError``.

    :param msg: The text to prepend to the exception message.
    :type msg: string

    """
    def real_decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                fn(self, *args, **kwargs)
            except mpd.CommandError as e:
                raise errors.CommandError('{0} Details: {1!s}'.format(msg, e))
            except mpd.ConnectionError as e:
                logger.warning('[mpd client] Connection error. Reconnecting...')
                self.client.connect(self.host, self.port, self.timeout)
                raise errors.CommandError('{0}. Connection error, restarted connection. ' +
                        'Details: {1!s}'.format(msg, e))
        return wrapper
    return real_decorator


def get_mpd_client(host, port, timeout, connect=True):
    """Helper function to return a connected MPD client instance.

    :param host: The hostname or IP of the MPD server.
    :type host: string
    :param port: The port of the MPD server.
    :type port: int
    :param timeout: The number of seconds to wait for a command to finish. Default: 15.
    :type timeout: int
    :param connect: Whether or not to connect to the server before returning.
    :type connect: bool

    """
    client = mpd.MPDClient()
    client.timeout = timeout
    client.idletimeout = None
    if connect:
        client.connect(host, port)
    return client


class StatusThread(threading.Thread):
    """A thread that runs in the background to check for song ending."""

    def __init__(self, host, port, timeout):
        super(StatusThread, self).__init__()
        self._stop = False
        self.client = get_mpd_client(host, port, timeout, connect=False)
        self.host = host
        self.port = port

    def run(self):
        """Start the thread."""
        logger.debug('[status thread] Starting.')
        self.client.connect(self.host, self.port)
        oldstate = self.client.status().get('state')
        while not self._stop:
            systems = self.client.idle()  # Blocking call
            if not 'player' in systems:
                continue
            status = self.client.status()
            newstate = status.get('state')
            if oldstate == 'play' and newstate == 'stop' and status.get('songid') is None:
                logger.debug('[status thread] Song has ended.')
                os.kill(os.getpid(), signals.SONG_ENDED)
            oldstate = newstate
        logger.debug('[status thread] Exiting.')

    def stop(self):
        """Stop the thread."""
        logger.debug('[status thread] Setting stop flag.')
        self._stop = True

    def is_stopped(self):
        """Return whether the thread is stopped."""
        return self._stop is True


class MPDPlayer(Player):

    def __init__(self, timeout=15, *args, **kwargs):
        """Create a new player process.

        :param timeout: The number of seconds to wait for a command to finish. Default: 15.
        :type timeout: int

        """
        # Initialize client
        self.host = '127.0.0.1'
        self.port = 6600
        self.timeout = timeout
        self.client = get_mpd_client(self.host, self.port, self.timeout)
        # Clear current playlist
        self.client.clear()
        # Start status thread
        self.status_thread = StatusThread(self.host, self.port, self.timeout)
        self.status_thread.start()

    @catch_mpd_error('Could not load & play song.')
    def load(self, path):
        """Load a file and play it.

        :param path: The path (url or filepath) to the file which should be played.
        :type path: string

        """
        logger.debug('[mpd player] Loading song {0}.'.format(path))
        # To prevent going back to the previous song (8tracks disallows it),
        # the playlist is cleared each time before loading the new track.
        try:
            self.client.clear()
        except mpd.CommandError as e:
            raise errors.CommandError('Could not clear playlist: {!s}'.format(e))
        self.client.add(path)
        self.client.play()

    @catch_mpd_error('Could not play or pause song.')
    def playpause(self):
        """Pause or resume the playback of a song."""
        logger.debug('[mpd player] Play/Pause.')
        self.client.pause()

    @catch_mpd_error('Could not stop playback.')
    def stop(self):
        """Stop playback."""
        logger.debug('[mpd player] Stop.')
        self.client.stop()

    @catch_mpd_error('Could not set volume.')
    def volume(self, amount):
        """Set the playback volume to ``amount`` percent.

        :param amount: The volume level, must be a number between 0 and 100.
        :type amount: int
        :raises: ValueError

        """
        logger.debug('[mpd player] Volume -> {0}.'.format(amount))
        try:
            amount = int(amount)
            assert 0 <= amount <= 100
        except (ValueError, AssertionError):
            raise ValueError('``amount`` must be an integer between 0 and 100.')
        self.client.setvol(amount)

    def terminate(self):
        """Terminate the instance."""
        logger.debug('[mpd player] Terminating.')
        self.status_thread.stop()
        self.client.close()
