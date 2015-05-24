# -*- coding: utf-8 -*-
"""
This module implements an MPD player. It uses the python-mpd2 library to talk
to the MPD server.
"""
from __future__ import print_function, division, absolute_import, unicode_literals

import contextlib
import functools
import logging
import os
import select
import socket
import threading

import mpd
import requests

from .. import errors, signals
from .interface import Player


# Set up logging
logger = logging.getLogger('orochi')


def catch_mpd_error(msg):
    """
    Decorator to catch MPD exceptions and convert them into a custom
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
                raise errors.CommandError('{0} Connection error. Details: {1!s}'.format(msg, e))
        return wrapper
    return real_decorator


def mpd_client_factory(timeout):
    """
    Helper function to return a connected MPD client instance.

    :param timeout: The number of seconds to wait for a command to finish. Default: 15.
    :type timeout: int

    """
    client = mpd.MPDClient()
    client.timeout = timeout
    client.idletimeout = None
    return client


class StatusThread(threading.Thread):
    """
    A thread that runs in the background to check for song ending.
    """
    def __init__(self, host, port, timeout):
        super(StatusThread, self).__init__()
        self._stop = False
        self.client = mpd_client_factory(timeout)
        self.host = host
        self.port = port

    def run(self):
        """
        Start the thread.
        """
        logger.debug('[status thread] Starting.')

        # Connect
        self.client.connect(self.host, self.port)

        # Store old state
        oldstate = self.client.status().get('state')

        # Send an asynchronous IDLE command
        self.client.send_idle('player')

        # Set the timeout for the select() command in seconds. This allows the
        # ``self._stop`` flag to be checked regularly. Not doing so would
        # result in an indefinitely blocked client if something goes wrong.
        select_timeout = 1.0

        while not self._stop:
            # Do a select() call to see if socket is ready
            changes = select.select([self.client], [], [], select_timeout)
            # If nothing has changed, loop again.
            if self.client not in changes[0]:
                continue
            # Otherwise, reset the IDLE command and query / process status.
            logger.debug('[status thread] Player status has changed.')
            self.client.noidle()
            status = self.client.status()
            newstate = status.get('state')
            if oldstate == 'play' and newstate == 'stop' and status.get('songid') is None:
                logger.debug('[status thread] Song has ended.')
                os.kill(os.getpid(), signals.SONG_ENDED)
            oldstate = newstate
            # Back to IDLE state.
            self.client.send_idle('player')
        logger.debug('[status thread] Exiting.')

    def stop(self):
        """
        Stop the thread.
        """
        logger.debug('[status thread] Setting stop flag.')
        self._stop = True

    def is_stopped(self):
        """
        Return whether the thread is stopped.
        """
        return self._stop is True


class MPDPlayer(Player):

    def __init__(self, timeout=15, *args, **kwargs):
        """
        Create a new player process.

        :param timeout: The number of seconds to wait for a command to finish. Default: 15.
        :type timeout: int

        """
        # Initialize client
        self.host = '127.0.0.1'
        self.port = 6600
        self.timeout = timeout
        self.client = mpd_client_factory(timeout)
        # Clear current playlist
        with self.connection():
            self.client.clear()
        # Start status thread
        self.status_thread = StatusThread(self.host, self.port, timeout)
        self.status_thread.start()

    @contextlib.contextmanager
    def connection(self):
        """
        Context manager to connect to and disconnect from MPD.
        """
        try:
            try:
                logger.debug('[mpd player/connection] Connecting to MPD...')
                self.client.connect(self.host, self.port)
            except (mpd.ConnectionError, socket.error) as e:
                logger.debug('[mpd player/connection] Exception %r while connecting' % e)
                raise errors.InitializationError('Could not connect to mpd: %s' % e)
            logger.debug('[mpd player/connection] Connected to MPD')
            yield
        finally:
            try:
                logger.debug('[mpd player/connection] Disconnecting from MPD')
                self.client.close()
                self.client.disconnect()
                logger.debug('[mpd player/connection] Disconnected from MPD')
            except mpd.ConnectionError:
                logger.debug('[mpd player/connection] mpd.ConnectionError')
                pass

    def _resolve_redirects(self, url):
        final_url = requests.head(url, allow_redirects=True).url
        return final_url

    @catch_mpd_error('Could not load & play song.')
    def load(self, path):
        """
        Load a file and play it.

        :param path: The path (url or filepath) to the file which should be played.
        :type path: string

        """
        logger.debug('[mpd player] Loading song {0}.'.format(path))
        url = self._resolve_redirects(path)
        logger.debug('[mpd player] URL resolves to {0}.'.format(url))
        with self.connection():
            # To prevent going back to the previous song (8tracks disallows it),
            # the playlist is cleared each time before loading the new track.
            try:
                self.client.clear()
            except mpd.CommandError as e:
                raise errors.CommandError('Could not clear playlist: {!s}'.format(e))
            logger.debug('[mpd player/load] Adding url to mpd playlist')
            self.client.add(url)
            logger.debug('[mpd player/load] Playing url')
            self.client.play()

    @catch_mpd_error('Could not play or pause song.')
    def playpause(self):
        """
        Pause or resume the playback of a song.
        """
        logger.debug('[mpd player] Play/Pause.')
        with self.connection():
            self.client.pause()

    @catch_mpd_error('Could not stop playback.')
    def stop(self):
        """
        Stop playback.
        """
        logger.debug('[mpd player] Stop.')
        with self.connection():
            self.client.stop()

    @catch_mpd_error('Could not set volume.')
    def volume(self, amount):
        """
        Set the playback volume to ``amount`` percent.

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
        with self.connection():
            self.client.setvol(amount)

    def terminate(self):
        """
        Terminate the instance.
        """
        logger.debug('[mpd player] Terminating.')
        self.status_thread.stop()
