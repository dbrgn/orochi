# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import re
import time
import signal
import threading
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

    def __init__(self, timeout=10, extra_arguments=''):
        """Create a new asynchronous MPlayer process.

        The mplayer process will be started in slave mode and with line
        buffering. It can be controlled with the methods provided by this
        class.

        Args:
            timeout:
                The number of seconds to wait for a command to finish. Default: 6.
            extra_arguments:
                Extra arguments that are passed on to the mplayer slave
                process.

        """
        self.timeout = timeout
        command = ['mplayer',
            '-slave', '-idle',
            '-really-quiet', '-msglevel', 'global=6:cplayer=4', '-msgmodule',
            '-input', 'nodefault-bindings',
            '-cache', '1024']
        if extra_arguments:
            command.extend(extra_arguments.split(' '))
        self.p = Process(command, bufsize=1)
        self.t = None
        self.write_lock = threading.Lock()

    def _send_command(self, command, *args):
        """Send a command to mplayer's stdin in a thread safe way. The function
        handles all necessary locking and automatically handles line breaks and
        string formatting.

        Args:
            command:
                The basic mplayer command, like "pause" or "loadfile", without
                a newline character.  This can contain new-style string
                formatting syntax like ``{}``.
            *args:
                Provide as many formatting arguments as you like. They are
                automatically ``quote()``d for security and passed to the
                string formatting function (printf-style).

        """
        with self.write_lock:
            safe_args = [quote(str(arg)) for arg in args]
            self.p.write(command.format(*safe_args) + '\n')

    def _stop_background_thread(self, blocking=True):
        """Abort the background thread by setting the ``self.t_stop`` event. If
        ``blocking`` is set, wait for it to finish."""
        if self.t is not None and self.t.is_alive():
            self.t_stop.set()
            if blocking:
                self.t.join()

    def load(self, path):
        """Load a file and play it.

        Args:
            path:
                The path (url or filepath) to the file which should be played.

        """
        # Fix https URLs, which are not supported by mplayer
        if path.startswith('https:'):
            path = 'http:' + path[6:]

        # Stop previously started background threads
        self._stop_background_thread()

        # Load file, wait for command to finish
        self._send_command('loadfile {}', path)
        start = time.time()
        while 1:
            if 'CPLAYER: Starting playback...' in self.p.read():
                break
            if time.time() - start > self.timeout:  # TODO use sigalarm or sigusr2 instead
                raise RuntimeError("Playback didn't start inside {}s. ".format(self.timeout) +
                        "Something must have gone wrong.", self.p.readerr())
                self.terminate()
            time.sleep(0.1)

        # Start a background thread that checks the playback status
        def playback_status(process, stop_event, write_lock):
            """Poll mplayer process for time_pos song and ending.

            When song has ended, send a SIGUSR1 signal. When time_pos is larger
            than 30s, send a SIGUSR2 signal to report the song.

            When ``stop_event`` is set, exit thread.

            """
            reported = False
            while not stop_event.is_set():
                if not reported:
                    with write_lock:
                        process.write('get_time_pos\n')
                stdout = process.read()
                if 'GLOBAL: EOF code: 1' in stdout:
                    os.kill(os.getpid(), signal.SIGUSR1)
                match = re.search(r'GLOBAL: ANS_TIME_POSITION=([0-9]+\.[0-9]+)', stdout)
                if not reported and match and float(match.groups()[0]) >= 30:
                    os.kill(os.getpid(), signal.SIGUSR2)
                    reported = True
                stop_event.wait(0.5)
        self.t_stop = threading.Event()
        thread_args = (self.p, self.t_stop, self.write_lock)
        self.t = threading.Thread(target=playback_status, args=thread_args)
        self.t.daemon = True
        self.t.start()

    def playpause(self):
        """Pause or resume the playback of a song."""
        self._send_command('pause')

    def stop(self):
        """Stop playback."""
        self._send_command('stop')
        self._stop_background_thread()

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
        self._send_command('volume {} 1', amount)

    def terminate(self):
        """Shut down mplayer and replace the reference to the async process
        with a dummy instance that raises a :class:`RuntimeError` on any method
        call."""
        if hasattr(self.p, 'terminate'):
            self._stop_background_thread()
            self.p.terminate()
            self.p = TerminatedException()

    def __del__(self):
        """Destructor. Calls ``self.terminate()``."""
        self.terminate()
