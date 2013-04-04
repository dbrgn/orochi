# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import sys
import time

import requests
import mpylayer


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
        self.current_track = None

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

    def play_mix(self, mix_id):
        play_token = self._obtain_play_token()
        data = self._get('sets/{token}/play.json'.format(token=play_token), {
            'mix_id': mix_id,
        })
        self.current_track = data['set']['track']
        print('Track url: ' + self.current_track['url'])
        #Track: {u'performer': u'Yukon Blonde', u'name': u'Brides Song', u'url': u'https://dtp6gm33au72i.cloudfront.net/tf/000/796/'


## Get song
#
#params = {'mix_id': mix['id']}
#r = requests.get(BASE_URL + 'sets/{token}/play.json'.format(token=play_token), params=params, headers=HEADERS)
#data_track = r.json()
#track = data_track['set']['track']
#
#print('Now playing "{track[name]}" by "{track[performer]}"...'.format(track=track))
#mp = mpylayer.MPlayerControl()
#mp.loadfile(track['url'])
#time.sleep(1)
#mp.pause()  # Start playback
#time.sleep(1)
#time.sleep(mp.length - 1)
