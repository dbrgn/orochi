# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import re
import time
import signal
import threading
import subprocess
try:
    from shlex import quote
except ImportError:  # Python < 3.3
    from pipes import quote

import requests

from .asyncproc import Process
from .errors import TerminatedError, InitializationError


class DeadMPlayer(object):
    """This is a "dummy object" that replaces the reference to the mplayer
    process as soon as the process is terminated.

    All it does is raising a :ex:`errors.TerminatedError` on any method call.

    """
    def __getattr__(self, attr):
        raise TerminatedError('MPlayer has been terminated and cannot be used anymore.')


class MPlayer(object):

    def __init__(self, timeout=15, extra_arguments=''):
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
        with open(os.devnull, 'w') as devnull:
            command = ['mplayer', '--version']
            retcode = subprocess.call(command, stdout=devnull, stderr=devnull, shell=True)
        if retcode == 127:
            msg = 'mplayer binary not found. Are you sure MPlayer is installed?'
            raise InitializationError(msg)
        self.timeout = timeout
        command = ['mplayer',
            '-slave', '-idle',
            '-really-quiet', '-msglevel', 'global=6:cplayer=4', '-msgmodule',
            '-input', 'nodefault-bindings',
            '-vo', 'null',
            '-cache', '1024']
        if extra_arguments:
            command.extend(extra_arguments.split(' '))
        self.p = Process(command, bufsize=1)
        self.t = None
        self.write_lock = threading.Lock()

        # Wait for MPlayer to start
        start = time.time()
        while True:
            if 'CPLAYER: MPlayer' in self.p.read():
                break
            elif time.time() - start > self.timeout:
                raise RuntimeError("MPlayer didn't start within {}s. ".format(self.timeout) +
                                   "Something must have gone wrong.", self.p.readerr())
            else:
                time.sleep(0.01)

        # Check for pausing_keep_force support in MPlayer
        has_pausing_keep_force = False
        self.p.write('pausing_keep_force get_prop thisshouldntexist\n')
        start = time.time()
        while time.time() - start < 0.1:
            # Any response from MPlayer means it understood 'pausing_keep_force'
            if 'GLOBAL: ANS_ERROR=PROPERTY_UNKNOWN' in self.p.read():
                has_pausing_keep_force = True
                break
            else:
                time.sleep(0.01)
        if has_pausing_keep_force:
            self.pausing_keep = 'pausing_keep_force'
        else:
            self.pausing_keep = 'pausing_keep'
            print("*** Warning: current version of MPlayer doesn't support 'pausing_keep_force'.\n"
                  "MPlayer will skip frames while paused. Upgrade to r27665 (1.0rc3) or higher.")

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
        # Resolve any redirects
        url = requests.head(path, allow_redirects=True).url

        # Fix https URLs, which are not supported by mplayer
        if url.startswith('https:'):
            url = 'http:' + url[6:]

        # Stop previously started background threads
        self._stop_background_thread()

        # Load file, wait for command to finish
        self._send_command('loadfile {}', url)
        start = time.time()
        while 1:
            if 'CPLAYER: Starting playback...' in self.p.read():
                break
            if time.time() - start > self.timeout:  # TODO use sigalarm or sigusr2 instead
                self.terminate()
                raise RuntimeError("Playback didn't start within {}s. ".format(self.timeout) +
                        "Something must have gone wrong. Are you experiencing network problems?")
            time.sleep(0.1)

        # Start a background thread that checks the playback status
        def playback_status(process, stop_event, write_lock, pausing_keep):
            """Poll mplayer process for time_pos song and ending.

            When song has ended, send a SIGUSR1 signal. When time_pos is larger
            than 30s, send a SIGUSR2 signal to report the song.

            When ``stop_event`` is set, exit thread.

            """
            reported = False
            time_pos_rex = re.compile(r'GLOBAL: ANS_TIME_POSITION=([0-9]+\.[0-9]+)')
            while not stop_event.is_set():
                if not reported:
                    with write_lock:
                        process.write('{} get_time_pos\n'.format(pausing_keep))
                stdout = process.read()
                if stdout:
                    if 'GLOBAL: EOF code: 1' in stdout:
                        os.kill(os.getpid(), signal.SIGUSR1)
                    if not reported:
                        match = time_pos_rex.search(stdout)
                        if match and float(match.group(1)) >= 30:
                            os.kill(os.getpid(), signal.SIGUSR2)
                            reported = True
                stop_event.wait(0.5)
        self.t_stop = threading.Event()
        thread_args = (self.p, self.t_stop, self.write_lock, self.pausing_keep)
        self.t = threading.Thread(target=playback_status, args=thread_args)
        self.t.daemon = True
        self.t.start()

    def playpause(self):
        """Pause or resume the playback of a song."""
        self._send_command('pause')

    def stop(self):
        """Stop playback."""
        self._send_command('{} stop', self.pausing_keep)
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
        self._send_command('{} volume {} 1', self.pausing_keep, amount)

    def terminate(self):
        """Shut down mplayer and replace the reference to the async process
        with a dummy instance that raises a :class:`RuntimeError` on any method
        call."""
        if hasattr(self, 'p') and hasattr(self.p, 'terminate'):
            self._stop_background_thread()
            self.p.terminate()
            self.p = DeadMPlayer()

    def __del__(self):
        """Destructor. Calls ``self.terminate()``."""
        self.terminate()
