#!/usr/bin/env python
# whisker_serial_order/settings.py

import os
from whisker_serial_order.constants import DB_URL_ENV_VAR

dbsettings = {
    # three slashes for a relative path
    'url': os.environ.get(DB_URL_ENV_VAR),
    # 'echo': True,
    'echo': False,
    'connect_args': {
        # 'timeout': 15,
    },
}


def set_database_url(url):
    global dbsettings
    dbsettings['url'] = url
