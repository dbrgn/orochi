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



#
#
## Choose mix
#
#mix_id = int(raw_input('Please choose a mix: '))
#mix = data_mixes['mixes'][mix_id - 1]
#
#
## Obtain a play token
#
#r = requests.get(BASE_URL + 'sets/new.json', headers=HEADERS)
#data_token = r.json()
#assert data_token['errors'] is None
#
#play_token = data_token['play_token']
#
#
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
