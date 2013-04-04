# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import sys

import requests


def env(key):
    try:
        return os.environ[key]
    except KeyError:
        print('Please set the {key} environment variable.'.format(key=key))
        sys.exit(-1)


class APIError(RuntimeError):
    """Raised when the API returns error messages."""
    pass


class EightTracksAPI(object):

    def __init__(self):
        self.base_url = 'https://8tracks.com/'
        self.s = requests.Session()
        self.s.headers.update({
            'X-Api-Key': env('EIGHTTRACKS_API_KEY'),
            'X-Api-Version': 2,
            'Accept': 'application/json',
        })
        self.play_token = None

    def _get(self, resource, params={}, **kwargs):
        """Do a GET request to the specified API resource.

        After the query is sent, the HTTP status is verified (a non-200 status
        raises an exception). Then the JSON data is unpacked and verified for
        errors.

        Args:
            resource:
                The resource that is appended to the base url (without any GET
                parameters).
            params:
                The GET parameters dictionary. Default: {}.
            **kwargs:
                Any other keyword arguments that should be passed directly to
                requests.

        Returns:
            The JSON response data.

        Raises:
            requests.exceptions.HTTPError:
                Raised if the request fails or if it returns a non-200 status
                code.
            simplejson.decoder.JSONDecodeError:
                Raised if JSON decoding fails.
            APIError:
                Raised when the API returns an error. The first argument is the
                error message, the second argument is the entire JSON response.

        """
        r = self.s.get(self.base_url + resource, params=params, **kwargs)
        r.raise_for_status()
        data = r.json()
        if 'errors' in data and data['errors'] is not None:
            raise APIError(data['errors'], data)
        return data

    def _obtain_play_token(self, force_refresh=False):
        """Return a new play token.

        If a play token has already been requested before, this token is
        returned, as long as ``force_refresh`` is ``False``.

        Args:
            force_refresh:
                Whether to ignore a cached play token and force the requesting
                of a new one. Default: False.

        Returns:
            A play token as a string.

        """
        if self.play_token is None or force_refresh:
            data = self._get('sets/new.json')
            self.play_token = data['play_token']
        return self.play_token

    def search_mix(self, query, sort='hot', page=1, per_page=20):
        """Search for a mix.

        Args:
            query:
                The search term to search for.
            sort:
                The sort order. Possible values: recent, popular, hot.
                Default: 'hot'.
            page:
                Which result page to return, if more than ``per_page`` are
                found.
            per_page:
                How many mixes to return per page. Default: 20.

        Returns:
            The list of matching mixes.

        """
        data = self._get('mixes.json', {
            'q': query,
            'sort': sort,
            'per_page': per_page,
        })
        return data['mixes']

    def _playback_control(self, mix_id, command):
        """Used to do play/next/skip requests.

        Args:
            mix_id:
                The 8tracks mix id to start playing.
            command:
                The command to execute (play/next/skip).

        Returns:
            Information about the set, including track data.

        """
        play_token = self._obtain_play_token()
        resource = 'sets/{token}/{command}.json'.format(token=play_token, command=command)
        data = self._get(resource, {
            'mix_id': mix_id,
        })
        return data['set']

    def play_mix(self, mix_id):
        """Start a mix playback.

        Args:
            mix_id:
                The 8tracks mix id to start playing.

        Returns:
            Information about the playing set, including track data.

        """
        return self._playback_control(mix_id, 'play')

    def next_track(self, mix_id):
        """Request the next track after a track has regularly finished playing.

        If you want to skip a track, use ``skip_track`` instead.

        Args:
            mix_id:
                The currently playing 8tracks mix id.

        Returns:
            New set information, including track data.

        """
        return self._playback_control(mix_id, 'next')

    def skip_track(self, mix_id):
        """Skip a track.

        Note that the caller has the responsibility to check whether the user
        is allowed to skip a track or not.

        Args:
            mix_id:
                The currently playing 8tracks mix id.

        Returns:
            New set information, including track data.

        """
        return self._playback_control(mix_id, 'skip')

    def report_track(self, mix_id, track_id):
        """Report a track as played.

        In order to be legal and pay royalties properly, 8tracks must report
        every performance of every song played to SoundExchange. A
        "performance" is counted when the 30 second mark of a song is reached.
        So at 30 seconds, you must call this function.

        Args:
            mix_id:
                The currently playing 8tracks mix id.
            track_id:
                The id of the track to report.

        Returns:
            TODO

        Raises:
            TODO

        """
        play_token = self._obtain_play_token()
        data = self._get('sets/{token}/report.json'.format(token=play_token), {
            'mix_id': mix_id,
            'track_id': track_id,
        })
        import ipdb; ipdb.set_trace()


#mp = mpylayer.MPlayerControl()
#mp.loadfile(track['url'])
#time.sleep(1)
#mp.pause()  # Start playback
#time.sleep(1)
#time.sleep(mp.length - 1)
