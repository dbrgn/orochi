#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
from setuptools import setup, find_packages
from orochi import meta

readme = io.open('README.rst', mode='r', encoding='utf8').read()

setup(name='orochi',
      version=meta.version,
      description=meta.description,
      author=meta.author,
      author_email=meta.author_email,
      url='https://github.com/dbrgn/orochi',
      packages=find_packages(),
      zip_safe=False,
      include_package_data=True,
      license=meta.license,
      keywords='orochi music playlists 8tracks eighttracks mplayer player',
      long_description=readme,
      install_requires=['requests>=1.2.0,<3'],
      entry_points={
          'console_scripts': [
              '%s = orochi.client:main' % meta.title,
          ]
      },
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'License :: OSI Approved :: GNU General Public License (GPL)',
          'Natural Language :: English',
          'Operating System :: MacOS',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 2.7',
          'Topic :: Internet',
          'Topic :: Multimedia :: Sound/Audio :: Players',
          'Topic :: Terminals',
      ],
)
