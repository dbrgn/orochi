# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
from string import Template

import requests
import mpylayer


# Helper functions

def env(key):
    try:
        return os.environ[key]
    except KeyError:
        print('Please set the {key} environment variable.'.format(key=key))
        sys.exit(-1)


# Configuration

HEADERS = {
    'X-Api-Key': env('EIGHTTRACKS_API_KEY'),
    'X-Api-Version': 2,
    'Accept': 'application/json',
}

BASE_URL = 'http://8tracks.com/'


# Search mixes

search = raw_input('Search keywords: ')
params = {
    'q': search,
    'sort': 'hot',
    'per_page': 20,
}
r = requests.get(BASE_URL + 'mixes.json', params=params, headers=HEADERS)
data_mixes = r.json()
assert data_mixes['errors'] is None

print('Found the following mixes:')
mix_info_tpl = Template(' $id) $name ($trackcount tracks, ${hours}h ${minutes}m)')
for i, mix in enumerate(data_mixes['mixes'], 1):
    hours = mix['duration'] // 60 // 60
    minutes = (mix['duration'] // 60) % 60
    mix_info = mix_info_tpl.substitute(id=i, name=mix['name'],
            trackcount=mix['tracks_count'], hours=hours, minutes=minutes)
    print(mix_info)


# Choose mix

mix_id = int(raw_input('Please choose a mix: '))
mix = data_mixes['mixes'][mix_id - 1]


# Obtain a play token

r = requests.get(BASE_URL + 'sets/new.json', headers=HEADERS)
data_token = r.json()
assert data_token['errors'] is None

play_token = data_token['play_token']


# Get song

params = {'mix_id': mix['id']}
r = requests.get(BASE_URL + 'sets/{token}/play.json'.format(token=play_token), params=params, headers=HEADERS)
data_track = r.json()
track = data_track['set']['track']

print('Now playing "{track[name]}" by "{track[performer]}"...'.format(track=track))
mp = mpylayer.MPlayerControl()
mp.loadfile(track['url'])
mp.pause()  # Play track
import ipdb; ipdb.set_trace()
