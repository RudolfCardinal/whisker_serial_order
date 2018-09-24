#!/usr/bin/env python
# whisker_serial_order/settings.py

"""
===============================================================================

    Copyright © 2016-2018 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

===============================================================================

Global settings for the serial order task.

"""

import os
from whisker_serial_order.constants import DB_URL_ENV_VAR, OUTPUT_DIR_ENV_VAR


dbsettings = {
    # three slashes for a relative path
    'url': os.environ.get(DB_URL_ENV_VAR),
    'echo': False,
    'connect_args': {
        # 'timeout': 15,
    },
}

filesettings = {
    'output_directory': os.environ.get(OUTPUT_DIR_ENV_VAR, os.getcwd()),
}


def set_database_url(url: str) -> None:
    """
    Sets the global SQLAlchemy database URL.

    Args:
        url: SQLAlchemy URL; see
            http://docs.sqlalchemy.org/en/latest/core/engines.html
    """
    global dbsettings
    dbsettings['url'] = url


def set_database_echo(echo: bool) -> None:
    """
    Sets the global database echo settings (for debugging).
    """
    global dbsettings
    dbsettings['echo'] = echo


def set_output_directory(directory: str) -> None:
    """
    Sets the output directory (where the safety copy of data is stored).
    """
    global filesettings
    filesettings['output_directory'] = directory


def get_output_directory() -> str:
    """
    Gets the output directory (where the safety copy of data is stored).
    """
    return filesettings['output_directory']
