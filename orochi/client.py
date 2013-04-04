# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import cmd
from string import Template
from textwrap import TextWrapper

from .api import EightTracksAPI


class CmdExitMixin(object):
    """A mixin for a Cmd instance that provides the exit and quit command."""

    def do_exit(self, s):
        return True

    def help_exit(self):
        print('Exit the interpreter.')
        print('You can also use the Ctrl-D shortcut.')

    do_EOF = do_exit
    help_EOF = help_exit
    do_quit = do_exit
    help_quit = help_exit


class Client(CmdExitMixin, cmd.Cmd, object):

    # Setup / configuration

    def preloop(self):
        print('Hello')
        self.api = EightTracksAPI()
        return super(Client, self).preloop()

    def precmd(self, line):
        self.console_width = int(os.popen('stty size', 'r').read().split()[1])
        return super(Client, self).precmd(line)

    def postloop(self):
        print('Goodbye')
        return super(Client, self).postloop()

    def emptyline(self):
        """Don't repeat last command on empty line."""
        pass

    # Actual commands

    def do_search(self, s):
        print('Results for "{}":'.format(s))
        mixes = self.api.search_mix(s)
        wrapper = TextWrapper(width=self.console_width - 5, subsequent_indent=(' ' * 5))
        mix_info_tpl = Template('$name ($trackcount tracks, ${hours}h ${minutes}m)')
        for i, mix in enumerate(mixes, 1):
            prefix = ' {0})'.format(i).ljust(5)
            hours = mix['duration'] // 60 // 60
            minutes = (mix['duration'] // 60) % 60
            mix_info = mix_info_tpl.substitute(name=mix['name'],
                    trackcount=mix['tracks_count'], hours=hours, minutes=minutes)
            print(prefix + wrapper.fill(mix_info))

    def help_search(self):
        print('Search for a mix.')


if __name__ == '__main__':
    client = Client()
    client.cmdloop()
