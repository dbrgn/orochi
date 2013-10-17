# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import sys
import cmd
import json
import signal
from string import Template
from getpass import getpass

from textwrap import TextWrapper
from requests import HTTPError, ConnectionError

from .api import EightTracksAPI, APIError
from .player import MPlayer
from .errors import InitializationError, TerminatedError
from .colors import bold


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

    DEFAULT_CONFIG_KEYS = ['mplayer_extra_arguments', 'username', 'password', 'autologin']

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
        self._logged_in = None
        self._user_name = ''
        self._password = ''
        # Try to login if autologin is on.
        if self.config['username'] and self.config['password'] and self.config['autologin']:
            self.do_login(self.config['username'], password=self.config['password'])
        return super(Client, self).preloop()

    def precmd(self, line):
        self.console_width = int(os.popen('stty size', 'r').read().split()[1])
        return super(Client, self).precmd(line)

    def cmdloop(self, intro=None):
        """Ignore Ctrl+C."""
        if intro is not None:
            self.intro = intro
        try:
            super(Client, self).cmdloop()
        except KeyboardInterrupt:
            print()  # Newline
            self.cmdloop(intro='')

    def emptyline(self):
        """Don't repeat last command on empty line."""
        pass

    # Actual commands

    def do_search(self, s):
        mixes = self.api.search_mix(s)

        print('Results for "{}":'.format(s))
        wrapper = TextWrapper(width=self.console_width - 5, subsequent_indent=(' ' * 5))
        mix_info_tpl = Template('$name ($trackcount tracks, ${hours}h ${minutes}m, by ${user})')

        self.mixes = {}
        for i, mix in enumerate(mixes, 1):
            # Cache mix ids
            self.mixes[i] = mix
            # Print line
            prefix = ' {0})'.format(i).ljust(5)
            hours = mix['duration'] // 60 // 60
            minutes = (mix['duration'] // 60) % 60
            mix_info = mix_info_tpl.substitute(name=bold(mix['name']), user=mix['user']['login'],
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
            try:
                i = PlayCommand(self.config, mix_id, self)
            except InitializationError as e:
                print('*** Error: {}'.format(e))
                return
            i.prompt = get_prompt(mix)
            i.cmdloop()

    def help_play(self):
        print('Syntax: play <mix>')
        print('The <mix> argument can either be a search result number from the last search,')
        print('a specific 8tracks mix ID or a mix URL from the website.')

    def do_login(self, s, password=None):
        """
        Raises:
            requests.exceptions.HTTPError:
                Raised if the request fails or server return a non-200 status code.
            requests.exceptions.ConnectionError:
                Raised if connection error.
        """
        if not s:
            self.help_login()
        else:
            self._user_name = s.strip()
            self._password = password or getpass('Password: ')
            try:
                self.api._obtain_user_token(self._user_name, self._password, force_refresh=True)
                print('Successfully logged in as %s!' % self._user_name)
                self._logged_in = True
            except HTTPError:
                self._logged_in = None
                print('Unable to login, please try again.')
            except ConnectionError:
                self._logged_in = None
                print("*** Could not connect to HTTP Host, connection error.")
            if self.config['autologin']:
                self.config['username'] = self._user_name
                self.config['password'] = self._password

    def help_login(self):
        print('Syntax: login <username>')
        print('Log in to your 8tracks account.')

    def do_autologin(self, s):
        if not s or s not in ('on', 'off'):
            self.help_autologin()
        elif s == 'on':
            self.config['autologin'] = 'True'
            self.config['username'] = self._user_name
            self.config['password'] = self._password
        elif s == 'off':
            self.config['autologin'] = ''
            self.config['password'] = ''
            self.config['username'] = ''

    def help_autologin(self):
        print('Syntax: autologin on|off')
        print('Toggle autologin on start (off by default).')
        print('WARNING: password will be saved in plain text.')
        print('When toggled off, password and username are deleted from config.')

    def get_login_status(self):
        return self._logged_in

    def do_liked_mixes(self, s):
        if not self._logged_in:
            print('You must first be logged in. Use login command.')
        else:
            mixes = self.api.get_liked_mixes()

            print('Results for "{}":'.format(s))
            wrapper = TextWrapper(width=self.console_width - 5, subsequent_indent=(' ' * 5))
            mix_info_tpl = Template('$name ($trackcount tracks, ${hours}h ' +
                                    '${minutes}m, by ${user})')

            self.mixes = {}
            for i, mix in enumerate(mixes, 1):
                # Cache mix ids
                self.mixes[i] = mix
                # Print line
                prefix = ' {0})'.format(i).ljust(5)
                hours = mix['duration'] // 60 // 60
                minutes = (mix['duration'] // 60) % 60
                mix_info = mix_info_tpl.substitute(
                        name=bold(mix['name']), user=mix['user']['login'],
                        trackcount=mix['tracks_count'],
                        hours=hours, minutes=minutes)
                print(prefix + wrapper.fill(mix_info))
                print(wrapper.fill('     Tags: {}'.format(mix['tag_list_cache'])))

    def help_liked_mixes(self):
        print('List liked mixes (login required).')


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

    def cmdloop(self):
        """Exit subcmd with Ctrl+C."""
        try:
            super(PlayCommand, self).cmdloop()
        except KeyboardInterrupt:
            self.do_stop()

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
        except TerminatedError:
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
        parts = []
        bold_track = {
            'name': bold(track['name'].strip()),
            'performer': bold(track['performer'].strip()),
        }
        parts.append('Now playing {0[name]} by {0[performer]}'.format(bold_track))
        if track['release_name']:
            parts.append('from the album {}'.format(bold(track['release_name'].strip())))
        if track['year']:
            parts.append('({0[year]})'.format(track))
        print(' '.join(parts) + '.')

    def help_status(self):
        print('Show the status of the currently playing song.')

    def do_mix_info(self, s=''):
        mix = self.api.get_mix_with_id(self.mix_id)
        print(bold(mix['name']))
        print('{0}'.format(mix['description']))
        print('http://8tracks.com{0}'.format(mix['path']))

    def help_mix_info(self):
        print('Show information about the currently playing mix.')

    def do_like_mix(self, s=''):
        if not self.parent_cmd.get_login_status():
            print('You must first be logged in. Use login command.')
        else:
            self.api.like_mix(self.mix_id)
            print('Mix liked.')

    def help_like_mix(self):
        print('Like the currently playing mix (login required).')

    def do_unlike_mix(self, s=''):
        if not self.parent_cmd.get_login_status():
            print('You must first be logged in. Use login command.')
        else:
            self.api.unlike_mix(self.mix_id)
            print('Mix removed from liked mixes.')

    def help_unlike_mix(self):
        print('Un-like the currently playing mix (login required).')

    def do_fav_track(self, s=''):
        if not self.parent_cmd.get_login_status():
            print('You must first be logged in. Use login command.')
        else:
            self.api.fav_track(self.status['track']['id'])
            print('Track favorited.')

    def help_fav_track(self):
        print('Favorite the currently playing track (login required).')

    def do_unfav_track(self, s=''):
        if not self.parent_cmd.get_login_status():
            print('You must first be logged in. Use login command.')
        else:
            self.api.unfav_track(self.status['track']['id'])
            print('Track removed from favorites.')

    def help_unfav_track(self):
        print('Un-favorite the currently playing track (login required).')

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

    def do_l(self, *args, **kwargs):
        self.do_like_mix(*args, **kwargs)

    def help_l(self):
        print('Alias for "like_mix".')

    def do_ul(self, *args, **kwargs):
        self.do_unlike_mix(*args, **kwargs)

    def help_ul(self):
        print('Alias for "unlike_mix".')

    def do_f(self, *args, **kwargs):
        self.do_fav_track(*args, **kwargs)

    def help_f(self):
        print('Alias for "fav_track".')

    def do_uf(self, *args, **kwargs):
        self.do_unfav_track(*args, **kwargs)

    def help_uf(self):
        print('Alias for "unfav_track".')


def main():
    client = Client()
    client.cmdloop()

if __name__ == '__main__':
    main()
