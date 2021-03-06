#!/usr/bin/env python
# tools/create_database_migration.py

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
"""

import argparse
import logging
import os
import subprocess
import sys

from cardinal_pythonlib.logs import configure_logger_for_colour

from whisker_serial_order.constants import DB_URL_ENV_VAR

if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")

N_SEQUENCE_CHARS = 4  # like Django

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
CODE_DIR = os.path.join(PROJECT_BASE_DIR, 'whisker_serial_order')
ALEMBIC_VERSIONS_DIR = os.path.join(CODE_DIR, 'alembic', 'versions')

if __name__ == '__main__':
    rootlogger = logging.getLogger()
    rootlogger.setLevel(logging.DEBUG)
    configure_logger_for_colour(rootlogger)  # configure root logger

    parser = argparse.ArgumentParser()
    parser.add_argument("message", help="Revision message")
    parser.add_argument(
        "--dburl", default=None,
        help="Database URL (if not specified, task will look in {} "
        "environment variable).".format(DB_URL_ENV_VAR))
    args = parser.parse_args()

    if args.dburl:
        os.environ[DB_URL_ENV_VAR] = args.dburl

    _, _, existing_version_filenames = next(os.walk(ALEMBIC_VERSIONS_DIR),
                                            (None, None, []))
    current_seq_strs = [x[:N_SEQUENCE_CHARS]
                        for x in existing_version_filenames]
    current_seq_strs.sort()
    if not current_seq_strs:
        current_seq_str = None
        new_seq_no = 1
    else:
        current_seq_str = current_seq_strs[-1]
        new_seq_no = max(int(x) for x in current_seq_strs) + 1
    new_seq_str = str(new_seq_no).zfill(N_SEQUENCE_CHARS)

    print("""
Generating new revision with Alembic...
    Last revision was: {}
    New revision will be: {}
    [If it fails with "Can't locate revision identified by...", you might need
    to DROP the alembic_version table.]
    """.format(current_seq_str, new_seq_str))

    sys.path.append(PROJECT_BASE_DIR)
    os.chdir(CODE_DIR)
    subprocess.call(['alembic', 'revision',
                     '--autogenerate',
                     '-m', args.message,
                     '--rev-id', new_seq_str])
