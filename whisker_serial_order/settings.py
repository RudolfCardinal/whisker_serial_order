#!/usr/bin/env python
# whisker_serial_order/settings.py

import os
from whisker_serial_order.constants import DB_URL_ENV_VAR, OUTPUT_DIR_ENV_VAR

dbsettings = {
    # three slashes for a relative path
    'url': os.environ.get(DB_URL_ENV_VAR),
    # 'echo': True,
    'echo': False,
    'connect_args': {
        # 'timeout': 15,
    },
}

filesettings = {
    'output_directory': os.environ.get(OUTPUT_DIR_ENV_VAR, os.getcwd()),
}


def set_database_url(url):
    global dbsettings
    dbsettings['url'] = url


def set_output_directory(directory):
    global filesettings
    filesettings['output_directory'] = directory


def get_output_directory():
    return filesettings['output_directory']
