# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import requests


class APIError(RuntimeError):
    """Raised when the API returns error messages."""
    pass


class EightTracksAPI(object):

    def __init__(self):
        self.base_url = 'https://8tracks.com/'
        self.s = requests.Session()
        self.s.headers.update({
            'X-Api-Key': 'da88fbe6cfd1996c0b6391372a8c7f3eb2dbc5be',
            'X-Api-Version': 2,
            'Accept': 'application/json',
        })
        self.play_token = None
        self._user_token = None

    def _get(self, resource, params=None, **kwargs):
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
        if params is None:
            params = {}
        r = self.s.get(self.base_url + resource, params=params, **kwargs)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            e.args = e.args + (r.json(),)
            raise e
        data = r.json()
        if 'errors' in data and data['errors'] is not None:
            raise APIError(data['errors'], data)
        return data

    def _post(self, resource, params={}, **kwargs):
        r = self.s.post(self.base_url + resource, params=params, **kwargs)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            e.args = e.args + (r.json(),)
            raise e
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

    def _obtain_user_token(self, username, password, force_refresh=False):
        """Request a new user token and pass it to the session header.

        If a user token has already been requested before, this token is
        passed, as long as ``force_refresh`` is ``False``.

        Args:
            force_refresh:
                Whether to ignore a cached user token and force the requesting
                of a new one. Default: False.
            username:
                Username needed to log in.
            password:
                Password needed to log in.

        """
        if self._user_token is None or force_refresh:
            # Logging out before trying to login. Otherwise logging in with a
            # new username won't work.
            self._post('logout')
            data = self._post('sessions.json', auth=(username, password))
            self._user_token = data['user_token']
            self.s.headers.update({'X-User-Token': self._user_token})

    def search_mix(self, query_type, query, sort, page, per_page):
        """Search for a mix by term, tag, user or user_liked.

        Args:
            query_type:
                The type of query. Possible values: tag, user, user_liked.
            query:
                The search term to search for (string or unicode). If the
                query_type is `tag`, then this parameter should be a comma
                separated string of tags to search for.
            sort:
                The sort order. Possible values: recent, popular, hot.
                Only works for tag search.
            page:
                Which result page to return, if more than ``per_page`` are
                found.
            per_page:
                How many mixes to return per page.

        Returns:
            Tuple containing three items:

            - The list of matching mixes.
            - The total number of results pages.
            - The next results page number.

        """
        params = {
            'sort': sort,
            'page': page,
            'per_page': per_page,
        }
        resource = 'mixes.json'

        if query_type == 'tag':
            parts = query.split(',')
            tags = filter(None, map(lambda p: p.strip(), parts))
            if len(tags) < 1:
                params['tag'] = query
            else:
                params['tags'] = '+'.join(tags)
        elif query_type == 'user':
            resource = 'users/{username}/mixes.json'.format(username=query)
        elif query_type == 'user_liked':
            params['view'] = 'liked'
            resource = 'users/{username}/mixes.json'.format(username=query)
        elif query_type == 'keyword':
            params['q'] = query

        data = self._get(resource, params)

        return data['mixes'], data['total_pages'], data['next_page']

    def get_mix_with_id(self, mix_id):
        """Find and return the mix with the specified ID.

        Args:
            mix_id:
                The 8tracks mix id.

        Returns:
            The mix object as returned by the API.

        """
        resource = 'mixes/{mix_id}.json'.format(mix_id=mix_id)
        data = self._get(resource)
        return data['mix']

    def get_mix_with_url(self, mix_url):
        """Find and return the mix with the specified ID.

        Args:
            mix_url:
                The 8tracks mix URL. Must start with "http(s)".

        Returns:
            The mix object as returned by the API.

        """
        r = self.s.get(mix_url)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            e.args = e.args + (r.json(),)
            raise e
        data = r.json()
        if 'errors' in data and data['errors'] is not None:
            raise APIError(data['errors'], data)
        return data['mix']

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

        Raises:
            requests.exceptions.HTTPError:
                Raised if the request fails or if it returns a non-200 status
                code. This is the case when the skipping limit has been
                exceeded.

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

        """
        play_token = self._obtain_play_token()
        self._get('sets/{token}/report.json'.format(token=play_token), {
            'mix_id': mix_id,
            'track_id': track_id,
        })

    def next_mix(self, mix_id):
        """Request the next mix similar to the current mix.

        Args:
            mix_id:
                The currently playing 8tracks mix id.

        Returns:
            The next mix.

        """
        play_token = self._obtain_play_token()
        resource = 'sets/{token}/next_mix.json'.format(token=play_token)
        data = self._get(resource, {
            'mix_id': mix_id,
        })
        return data['next_mix']

    def like_mix(self, mix_id):
        """Like the current mix.

        Args:
            mix_id:
                The currently playing 8tracks mix id.
        """
        self._post('mixes/{token}/like.json'.format(token=mix_id))

    def unlike_mix(self, mix_id):
        """Un-like the current mix.

        Args:
            mix_id:
                The currently playing 8tracks mix id.
        """
        self._post('mixes/{token}/unlike.json'.format(token=mix_id))

    def fav_track(self, track_id):
        """Favorite the current track.

        Args:
            track_id:
                The currently playing 8tracks track id.
        """
        self._post('tracks/{token}/fav.json'.format(token=track_id))

    def unfav_track(self, track_id):
        """Un-favorite the current track.

        Args:
            track_id:
                The currently playing 8tracks track id.
        """
        self._post('tracks/{token}/unfav.json'.format(token=track_id))
