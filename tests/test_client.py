# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import pytest

from orochi import client


@pytest.mark.parametrize(('name', 'expected'), [
    ('Short Mix', '(8tracks:Short Mix)> '),
    ('Name is exactly 30 characters!', '(8tracks:Name is exactly 30 characters!)> '),
    ('Name is longer than 30 characters!', '(8tracks:Name is longer than 30 charact...)> '),
])
def test_short_mix_prompt(name, expected):
    """Test the get_prompt functionality."""
    data = {'id': 42, 'name': name}
    prompt = client.get_prompt(data)
    assert prompt == expected
