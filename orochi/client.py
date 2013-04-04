# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import cmd
import time
from string import Template
from textwrap import TextWrapper
try:
    from shlex import quote
except ImportError:  # Python < 3.3
    from pipes import quote

from .api import EightTracksAPI
from .asyncproc import Process


LOADFILE_TIMEOUT = 6


class CmdExitMixin(object):
    """A mixin for a Cmd instance that provides the exit and quit command."""

    def do_exit(self, s):
        print('Goodbye.')
        return True

    def help_exit(self):
        print('Exit the interpreter.')
        print('You can also use the Ctrl-D shortcut.')

    do_EOF = do_exit
    help_EOF = help_exit


class Client(CmdExitMixin, cmd.Cmd, object):

    # Setup / configuration

    intro = 'Welcome! Type "help" for more information.'

    prompt = '(8tracks)> '

    def preloop(self):
        self.api = EightTracksAPI()
        self.mix_ids = {}
        self.volume = 100
        return super(Client, self).preloop()

    def precmd(self, line):
        self.console_width = int(os.popen('stty size', 'r').read().split()[1])
        return super(Client, self).precmd(line)

    def emptyline(self):
        """Don't repeat last command on empty line."""
        pass

    # Actual commands

    def do_search(self, s):
        mixes = self.api.search_mix(s)

        print('Results for "{}":'.format(s))
        wrapper = TextWrapper(width=self.console_width - 5, subsequent_indent=(' ' * 5))
        mix_info_tpl = Template('$name ($trackcount tracks, ${hours}h ${minutes}m)')

        self.mix_ids = {}
        for i, mix in enumerate(mixes, 1):
            # Cache mix ids
            self.mix_ids[i] = mix['id']
            # Print line
            prefix = ' {0})'.format(i).ljust(5)
            hours = mix['duration'] // 60 // 60
            minutes = (mix['duration'] // 60) % 60
            mix_info = mix_info_tpl.substitute(name=mix['name'],
                    trackcount=mix['tracks_count'], hours=hours, minutes=minutes)
            print(prefix + wrapper.fill(mix_info))

    def help_search(self):
        print('Syntax: search <searchterm>')
        print('Search for a mix. You can then play a mix with the "play" command.')

    def do_play(self, s):
        try:
            mix_id = self.mix_ids[int(s)]
        except ValueError:
            print('*** Invalid mix number: Please run a search first and then '
                  'specify a mix number to play.')
        except KeyError:
            print('*** Mix with number {i} not found: Did you run a search yet?'.format(i=s))
        else:
            i = PlayCommand(mix_id, self)
            i.prompt = '{0}:{1})> '.format(self.prompt[:-3], mix_id)
            i.cmdloop()

    def help_play(self):
        print('Syntax: play <mix_number>')
        print('Play the nth mix from the last search results.')


class PlayCommand(cmd.Cmd, object):

    def __init__(self, mix_id, parent_cmd, *args, **kwargs):
        self.mix_id = mix_id
        self.parent_cmd = parent_cmd
        self.api = parent_cmd.api

        r = super(PlayCommand, self).__init__(*args, **kwargs)

        # Initialize mplayer slave session with line buffer
        self.p = Process(['mplayer', '-slave', '-quiet', '-idle', '-cache', '1024'], bufsize=1)

        # Play first track at max volume
        self.status = self.api.play_mix(mix_id)
        self._play(self.status['track']['url'])
        self.p.write('volume {} 1\n'.format(self.parent_cmd.volume))
        self.do_status()

        return r

    def emptyline(self):
        """Don't repeat last command on empty line."""
        pass

    def _play(self, url):
        """Play the specified file using mplayer's ``loadfile`` and wait for
        the command to finish.

        Args:
            url:
                The URL of the file to play.

        Raises:
            RuntimeError:
                Raised if the loadfile command didn't return inside
                `LOADFILE_TIMEOUT` seconds. This is done by checking the
                subprocess' stdout for `Starting playback...`. The second
                argument to RuntimeError is mplayer's stdout.

        """
        if url.startswith('https'):
            url = 'http' + url[5:]
        self.p.write('loadfile {}\n'.format(quote(url)))

        # Wait for loadfile command to finish
        start = time.time()
        while 1:
            if self.p.read().endswith('Starting playback...\n'):
                break
            if time.time() - start > LOADFILE_TIMEOUT:
                raise RuntimeError("Playback didn't start inside {}s. ".format(LOADFILE_TIMEOUT) +
                        "Something must have gone wrong.", self.p.readerr())
            time.sleep(0.1)

    def do_pause(self, s):
        self.p.write('pause\n')

    def help_pause(self):
        print('Pause or resume the playback.')

    def do_stop(self, s):
        print('Stopping playback...')
        self.p.write('stop\n')
        self.p.terminate()
        return True

    def help_stop(self):
        print('Stop the playback and exit play mode.')

    def do_skip(self, s):
        print('Skipping track...')
        self.status = self.api.skip_track(self.mix_id)
        self._play(self.status['track']['url'])
        self.do_status()

    def help_skip(self):
        print('Skip the current song.')

    def do_volume(self, s):
        try:
            vol = int(s)
            assert 0 <= vol <= 100
        except (ValueError, AssertionError):
            print('*** ValueError: Argument must be a number between 0 and 100.')
        else:
            self.parent_cmd.volume = vol
            self.p.write('volume {} 1\n'.format(vol))

    def help_volume(self):
        print('Syntax: volume <amount>')
        print('Change playback volume. The argument must be a number between 0 and 100.')

    def do_status(self, s=''):
        track = self.status['track']
        print('Now playing "{0[name]}" by "{0[performer]}".'.format(track))

    def help_status(self):
        print('Show the status of the currently playing song.')

    do_EOF = do_stop
    help_EOF = help_stop


if __name__ == '__main__':
    client = Client()
    client.cmdloop()
