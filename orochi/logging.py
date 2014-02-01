# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import, unicode_literals

import os
import logging


def setup(directory):
    """Set up logging into a logfile."""
    logger = logging.getLogger('orochi')
    logfile = os.path.join(directory, 'debug.log')
    hdlr = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)


def get_logger():
    return logging.getLogger('orochi')
