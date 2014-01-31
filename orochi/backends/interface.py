# -*- coding: utf-8 -*-
"""
This module contains a generic interface with an abstract class that defines
all methods that a player implementation needs to be able to handle.
"""
from __future__ import print_function, division, absolute_import, unicode_literals

import abc


class Player(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def load(self, path):
        """Load a file and play it.

        Args:
            path:
                The path (url or filepath) to the file which should be played.

        """

    @abc.abstractmethod
    def playpause(self):
        """Pause or resume the playback of a song."""

    @abc.abstractmethod
    def stop(self):
        """Stop playback."""

    @abc.abstractmethod
    def volume(self, amount):
        """Set the playback volume to ``amount`` percent.

        Args:
            amount:
                The volume level, must be a number between 0 and 100.

        Raises:
            ValueError:
                Raised when ``amount`` is invalid.

        """

    @abc.abstractmethod
    def terminate(self):
        """Terminate the instance."""
