# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import sys
import cmd
import json
import signal
from string import Template
from textwrap import TextWrapper

from .api import EightTracksAPI
from .player import MPlayer


class ConfigFile(object):
    """Wrap a json based config file. Behave like a dictionary. Persist data on
    each write."""

    def __init__(self, filename='config.json'):
        self.filename = filename

        if not os.path.isfile(self.filename):
            self.config = {}
        else:
            with open(self.filename, 'r') as configfile:
                conf = ' '.join(configfile.xreadlines())
                if conf == '':
                    self.config = {}
                else:
                    try:
                        self.config = json.loads(conf)
                    except ValueError:
                        raise ValueError('"{}" could not be parsed. Is it a valid JSON file?' \
                                         .format(self.filename))

    def __getitem__(self, key):
        return self.config.get(key, '')

    def __setitem__(self, key, value):
        self.config[key] = value
        self._persist()

    def _persist(self):
        """Write current configuration to file."""
        with open(self.filename, 'w') as configfile:
            configfile.write(json.dumps(self.config, indent=2))


class CmdExitMixin(object):
    """A mixin for a Cmd instance that provides the exit and quit command."""

    def do_exit(self, s=''):
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
        self.volume = None
        self.config = ConfigFile()
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
            print(wrapper.fill('     Tags: {}'.format(mix['tag_list_cache'])))

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

    # Setup / configuration

    def __init__(self, mix_id, parent_cmd, *args, **kwargs):
        self.mix_id = mix_id
        self.parent_cmd = parent_cmd
        self.api = parent_cmd.api

        r = super(PlayCommand, self).__init__(*args, **kwargs)

        # Initialize mplayer
        self.p = MPlayer()

        # Register signal handlers
        signal.signal(signal.SIGUSR1, self._song_end_handler)
        signal.signal(signal.SIGUSR2, self._song_report_handler)

        # Play first track
        self.status = self.api.play_mix(mix_id)
        self.p.load(self.status['track']['url'])
        if self.parent_cmd.volume is not None:
            self.p.volume(self.parent_cmd.volume)
        self.do_status()

        return r

    def emptyline(self):
        """Don't repeat last command on empty line."""
        pass

    # Helper methods

    def _song_end_handler(self, signum, frame):
        """Signal handler for SIGUSR1. Advance to the next track, if
        available."""
        print('')
        print('Song has ended!')
        if self.status['at_last_track']:
            print('Playlist has ended!')
            self.do_stop()
        else:
            self.status = self.api.next_track(self.mix_id)
            self.p.load(self.status['track']['url'])
            self.do_status()
        print(self.prompt, end='')
        sys.stdout.flush()

    def _song_report_handler(self, signum, frame):
        """Signal handler for SIGUSR2. Report track play after 30 seconds."""
        print('\nReporting song...')
        self.api.report_track(self.mix_id, self.status['track']['id'])
        print(self.prompt, end='')
        sys.stdout.flush()

    # Actual commands

    def do_pause(self, s=''):
        self.p.playpause()

    def help_pause(self):
        print('Pause or resume the playback.')

    def do_stop(self, s=''):
        print('Stopping playback...')

        # Reset signal handling
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
        signal.signal(signal.SIGUSR2, signal.SIG_DFL)

        # Stop playback, terminate mplayer
        self.p.stop()
        self.p.terminate()

        # Return to main loop
        return True

    def help_stop(self):
        print('Stop the playback and exit play mode.')

    def do_skip(self, s=''):
        if not self.status['skip_allowed']:
            print('Sorry, skipping not allowed due to legal reasons. You may only skip '
                  '3 times during a 60 minute time frame.')
        elif self.status['at_last_track']:
            print('Playlist has ended!')
            return True
        else:
            print('Skipping track...')
            self.status = self.api.skip_track(self.mix_id)
            self.p.load(self.status['track']['url'])
            self.do_status()

    def help_skip(self):
        print('Skip the current song.')

    def do_volume(self, s):
        try:
            self.p.volume(s)
        except ValueError:
            print('*** ValueError: Argument must be a number between 0 and 100.')
        else:
            self.parent_cmd.volume = int(s)

    def help_volume(self):
        print('Syntax: volume <amount>')
        print('Change playback volume. The argument must be a number between 0 and 100.')

    def do_status(self, s=''):
        track = self.status['track']
        print('Now playing "{0[name]}" by "{0[performer]}".'.format(track))

    def help_status(self):
        print('Show the status of the currently playing song.')

    def do_debug(self, s=''):
        import ipdb; ipdb.set_trace()

    def help_debug(self):
        print('Start an interactive ipdb session.')

    do_EOF = do_stop
    help_EOF = help_stop


if __name__ == '__main__':
    client = Client()
    client.cmdloop()
