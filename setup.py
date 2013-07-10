#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from orochi import meta

f = open('requirements.txt', 'r')
lines = f.readlines()
requirements = [l.strip().strip('\n') for l in lines if l.strip() and not l.strip().startswith('#')]
readme = open('README.rst').read()

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
      install_requires=requirements,
      entry_points={
          'console_scripts': [
              '%s = orochi.client:main' % meta.title,
          ]
      },
      classifiers=[
          'Development Status :: 3 - Alpha',
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
