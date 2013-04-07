# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import time
try:
    from shlex import quote
except ImportError:  # Python < 3.3
    from pipes import quote

from .asyncproc import Process


class TerminatedException(object):
    """This is a "dummy object" that replaces the reference to the mplayer
    process as soon as the process is terminated.

    All it does is raising a RuntimeError on any method call.

    """
    def __getattr__(self, attr):
        raise RuntimeError('MPlayer has been terminated and cannot be used anymore.')


class MPlayer(object):

    def __init__(self, timeout=10):
        """Create a new asynchronous MPlayer process.

        The mplayer process will be started in slave mode and with line
        buffering. It can be controlled with the methods provided by this
        class.

        Args:
            timeout:
                The number of seconds to wait for a command to finish. Default: 6.

        """
        print('initializing...')
        self.timeout = timeout
        self.p = Process(['mplayer',
            '-slave', '-idle',
            '-really-quiet', '-msglevel', 'global=6:cplayer=4', '-msgmodule',
            '-input', 'nodefault-bindings',
            '-cache', '1024',
        ], bufsize=1)

    def load(self, path):
        """Load a file and play it.

        Args:
            path:
                The path (url or filepath) to the file which should be played.

        """
        if path.startswith('https:'):
            path = 'http:' + path[6:]
        self.p.write('loadfile {}\n'.format(quote(path)))
        # Wait for loadfile command to finish
        start = time.time()
        while 1:
            if 'CPLAYER: Starting playback...' in self.p.read():
                break
            if time.time() - start > self.timeout:
                self.terminate()
                raise RuntimeError("Playback didn't start inside {}s. ".format(self.timeout) +
                        "Something must have gone wrong.", self.p.readerr())
            time.sleep(0.1)

    def playpause(self):
        """Pause or resume the playback of a song."""
        self.p.write('pause\n')

    def stop(self):
        """Stop playback."""
        self.p.write('stop\n')

    def volume(self, amount):
        """Set the playback volume to ``amount`` percent.

        Args:
            amount:
                The volume level, must be a number between 0 and 100.

        Raises:
            ValueError:
                Raised when ``amount`` is invalid.

        """
        try:
            amount = int(amount)
            assert 0 <= amount <= 100
        except (ValueError, AssertionError):
            raise ValueError('``amount`` must be a number between 0 and 100.')
        self.p.write('volume {} 1\n'.format(amount))

    def terminate(self):
        """Shut down mplayer and replace the reference to the async process
        with a dummy instance that raises a :class:`RuntimeError` on any method
        call."""
        if hasattr(self.p, 'terminate'):
            self.p.terminate()
            self.p = TerminatedException()

    def __del__(self):
        """Destructor. Calls ``self.terminate()``."""
        self.terminate()
