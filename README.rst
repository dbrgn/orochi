Orochi – 8tracks.com commandline client
=======================================

**Warning: Alpha quality!**

Orochi is a command line client for `8tracks.com <http://8tracks.com/>`__
written in Python.

Yamata no Orochi (八岐の大蛇) is a legendary 8-headed and 8-tailed Japanese
dragon. The name translates to "8-branched giant snake". I chose the name
because it both refers to the number eight (as in 8tracks) and to snakes (as in
Python).

.. figure:: http://i.imgur.com/UdiIM8k.png
    :alt: Illustration of Yamata no Orochi

    *Image courtesy of Gustavo Araujo*


Usage
-----

Install::

    $ pip install -r requirements.txt

Start::

    $ python -m orochi.client

Available commands (main menu)::

    search:
        Syntax: search <searchterm>
        Search for a mix. You can then play a mix with the "play" command.
    play:
        Syntax: play <mix_number>
        Play the nth mix from the last search results.
    exit:
        Exit the interpreter.
        You can also use the Ctrl-D shortcut.

Available commands (play mode menu)::

    pause:
        Pause or resume the playback.
    stop:
        Stop the playback and exit play mode.
    skip:
        Skip the current song.
    status:
        Show the status of the currently playing song.
    volume:
        Syntax: volume <amount>
        Change playback volume. The argument must be a number between 0 and 100.


Coding Guidelines
-----------------

PEP8 via `flake8 <https://pypi.python.org/pypi/flake8>`_ with max-line-width set
to 99 and E126-E128 ignored.


License
-------

Copyright (C) 2013 Danilo Bargen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
