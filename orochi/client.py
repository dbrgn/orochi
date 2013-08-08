# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import sys
import cmd
import json
import signal
from string import Template
from textwrap import TextWrapper
from requests import HTTPError, ConnectionError

from .api import EightTracksAPI, APIError
from .player import MPlayer, TerminatedException


# Tuple containing prefix, main text and suffix for command line prompt
DEFAULT_PROMPT = ('(', '8tracks', ')> ')


def get_prompt(mix):
    """Return a prompt text based on the specified mix dictionary.

    Args:
        mix:
            Dictionary returned from 8tracks api containing mix information.

    Returns:
        A string that can be used as prompt.

    """
    # Get default prompt parts
    parts = list(DEFAULT_PROMPT)

    # Get and shorten mix name if necessary
    NAME_MAX_LENGTH = 30  # Hardcoded for now
    name = mix['name'][:NAME_MAX_LENGTH]
    if len(mix['name']) > NAME_MAX_LENGTH:
        name += '...'

    # Reassemble and return prompt parts
    parts[1] += ':{}'.format(name)
    return ''.join(parts)


class ConfigFile(object):
    """Wrap a json based config file. Behave like a dictionary. Persist data on
    each write."""

    DEFAULT_CONFIG_KEYS = ['mplayer_extra_arguments', 'username', 'password']

    def __init__(self, filename=None):
        if not filename:
            xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
            if not xdg_config_home:
                xdg_config_home = os.path.join(os.path.expanduser('~'), '.config')
            configdir = os.path.join(xdg_config_home, 'orochi')
            if not os.path.isdir(configdir):
                os.makedirs(configdir)
            filename = os.path.join(configdir, 'config.json')
        self.filename = filename

        # Parse existing config file
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
                        raise ValueError('"{}" could not be parsed. Is it a valid JSON file?'
                                         .format(self.filename))

        # Populate configfile with default values
        for key in self.DEFAULT_CONFIG_KEYS:
            self.config[key] = self.config.get(key, '')
        self._persist()

    def __getitem__(self, key):
        return self.config.get(key, '')

    def __setitem__(self, key, value):
        self.config[key] = value
        self._persist()

    def _persist(self):
        """Write current configuration to file."""
        file_existed = os.path.isfile(self.filename)
        with open(self.filename, 'w') as configfile:
            configfile.write(json.dumps(self.config, indent=2))
        # Make sure to set permissions that don't allow anyone else to see
        # content.
        if not file_existed:
            os.chmod(self.filename, 0600)

    def get(self, *args):
        return self.config.get(*args)


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

    prompt = ''.join(DEFAULT_PROMPT)

    def preloop(self):
        self.api = EightTracksAPI()
        self.mixes = {}
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

        self.mixes = {}
        for i, mix in enumerate(mixes, 1):
            # Cache mix ids
            self.mixes[i] = mix
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
        # The logic could be simplified here, and not have to re-catch all the exceptions
        # But, it makes the error messages clearer if we know where we went wrong.
        is_valid = False
        if not s:
            self.help_play()
        elif s.startswith('http'):
            try:
                # Assuming it's a mixURL
                mix = self.api.get_mix_with_url(s)
                mix_id = mix['id']
                is_valid = True
            except APIError:
                print('*** Invalid URL specified.')
            except HTTPError:
                print('*** Server returned a non-200 status code.')
            except ConnectionError:
                print('*** Couldn\'t connect to HTTP Host, connection error.')
            except (KeyError, ValueError):
                print('*** Invalid data was returned for URL')
        else:
            try:
                typed_val = int(s)
                # The 10 here really probably needs to be a config file option
                if 0 < typed_val <= 10:
                    mix = self.mixes[typed_val]
                    mix_id = mix['id']
                    is_valid = True
                else:
                    mix_id = typed_val
                    mix = self.api.get_mix_with_id(mix_id)
                    is_valid = True
            except ValueError:
                print('*** Invalid mix number: Please run a search first and then '
                      'specify a mix number to play.')
            except KeyError:
                print('*** Mix with number {i} not found: Did you run a search yet?'.format(i=s))
            except HTTPError:
                print('*** Mix with id {mix_id} not found.'.format(mix_id=s))
        if is_valid:
            i = PlayCommand(self.config, mix_id, self)
            i.prompt = get_prompt(mix)
            i.cmdloop()

    def help_play(self):
        print('Syntax: play <mix>')
        print('The <mix> argument can either be a search result number from the last search,')
        print('a specific 8tracks mix ID or a mix URL from the website.')


class PlayCommand(cmd.Cmd, object):

    # Setup / configuration

    def __init__(self, config, mix_id, parent_cmd, *args, **kwargs):
        self.mix_id = mix_id
        self.parent_cmd = parent_cmd
        self.api = parent_cmd.api

        r = super(PlayCommand, self).__init__(*args, **kwargs)

        # Initialize mplayer
        self.p = MPlayer(extra_arguments=config['mplayer_extra_arguments'])

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
            self.do_next_mix()
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
        try:
            self.p.stop()
            self.p.terminate()
        except TerminatedException:
            pass  # We wanted to stop the process anyways.

        # Return to main loop
        return True

    def help_stop(self):
        print('Stop the playback and exit play mode.')

    def do_next_song(self, s=''):
        if not self.status['skip_allowed']:
            print('Sorry, skipping not allowed due to legal reasons. You may only skip '
                  '3 times during a 60 minute time frame.')
            print('See http://8tracks.com/licensing for more information.')
        elif self.status['at_last_track']:
            print('Playlist has ended!')
            return True
        else:
            print('Skipping track...')
            self.status = self.api.skip_track(self.mix_id)
            self.p.load(self.status['track']['url'])
            self.do_status()

    def help_next_song(self):
        print('Skip to next song.')

    def do_next_mix(self, s=''):
        print('Skipping to the next mix...')
        mix = self.api.next_mix(self.mix_id)
        self.mix_id = mix['id']
        self.prompt = get_prompt(mix)

        self.status = self.api.play_mix(self.mix_id)
        self.p.load(self.status['track']['url'])
        self.do_status()

    def help_next_mix(self):
        print('Skip to next mix.')

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
        info = 'Now playing "{0[name]}" by "{0[performer]}", ' + \
               'from the album "{0[release_name]}" ({0[year]}).'
        print(info.format(track))

    def help_status(self):
        print('Show the status of the currently playing song.')

    def do_debug(self, s=''):
        try:
            import ipdb as pdb
        except ImportError:
            import pdb
        pdb.set_trace()

    def help_debug(self):
        print('Start an interactive (i)pdb session. Only used during development.')

    do_EOF = do_stop
    help_EOF = help_stop

    # Command aliases
    # TODO these methods could be generated in the constructor using a mapping

    def do_n(self, *args, **kwargs):
        self.do_next_song(*args, **kwargs)

    def help_n(self):
        print('Alias for "next_song".')

    def do_p(self, *args, **kwargs):
        self.do_pause(*args, **kwargs)

    def help_p(self):
        print('Alias for "pause".')

    def do_s(self, *args, **kwargs):
        self.do_status(*args, **kwargs)

    def help_s(self):
        print('Alias for "status".')

    def do_v(self, *args, **kwargs):
        self.do_volume(*args, **kwargs)

    def help_v(self):
        print('Alias for "volume".')


def main():
    client = Client()
    client.cmdloop()

if __name__ == '__main__':
    main()
