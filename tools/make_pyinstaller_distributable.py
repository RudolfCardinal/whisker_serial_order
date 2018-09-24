#!/usr/bin/env python
# tools/make_pyinstaller_distributable.py

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

Run this under Linux to make a Linux distributable, and under Windows to make
a Windows distributable.

"""

import logging
import os
import platform
import shutil
import subprocess
import sys

from cardinal_pythonlib.fileops import pushd
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from whisker_serial_order.version import SERIAL_ORDER_VERSION

log = logging.getLogger(__name__)

if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")
LINUX = platform.system() == 'Linux'
PLATFORM = platform.system().lower()
if LINUX:
    PYINSTALLER_EXTRA_OPTIONS = []
    ZIPFORMAT = "gztar"
    ZIPEXT = "tar.gz"
else:  # Windows
    PYINSTALLER_EXTRA_OPTIONS = ['--noconsole']
    ZIPFORMAT = "zip"
    ZIPEXT = "zip"

PYTHON = sys.executable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # .../tools
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))  # .../  # noqa
BUILD_DIR = os.path.join(PROJECT_BASE_DIR, 'build')
DIST_DIR = os.path.join(PROJECT_BASE_DIR, 'dist')
DIST_SUBDIR = os.path.join(DIST_DIR, 'whisker_serial_order')
LAUNCHFILE = os.path.join(DIST_SUBDIR, 'whisker_serial_order')

CWD_FOR_PYINSTALLER = PROJECT_BASE_DIR

SPECFILE = os.path.join(PROJECT_BASE_DIR, 'whisker_serial_order.spec')
WARNFILE = os.path.join(BUILD_DIR, 'whisker_serial_order',
                        'warn_whisker_serial_order.txt')
ZIPFILEBASE = os.path.join(
    DIST_DIR,
    'whisker_serial_order_{VERSION}_{PLATFORM}'.format(
        VERSION=SERIAL_ORDER_VERSION,
        PLATFORM=PLATFORM,
        ZIPEXT=ZIPEXT,
    )
)


def main():
    log.info("Deleting old distribution...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_SUBDIR, ignore_errors=True)  # NOT DIST_DIR
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    log.info("Building new distribution...")
    args = (
        ['pyinstaller', '--clean', '--log-level=INFO'] +
        PYINSTALLER_EXTRA_OPTIONS +
        [SPECFILE]
    )
    with pushd(CWD_FOR_PYINSTALLER):
        log.debug("In directory: {}".format(os.getcwd()))
        log.debug("Running PyInstaller with args: {!r}".format(args))
        subprocess.check_call(args)

    log.info("Zipping to {!r}...".format(ZIPFILEBASE))
    zipfile = shutil.make_archive(ZIPFILEBASE, ZIPFORMAT, DIST_SUBDIR)

    log.info("""
The {DIST_SUBDIR} directory should contain everything you need to run.
Run with: {LAUNCHFILE}
Look for warnings in: {WARNFILE}
To distribute, use {zipfile}
    """.format(
        DIST_SUBDIR=DIST_SUBDIR,
        LAUNCHFILE=LAUNCHFILE,
        WARNFILE=WARNFILE,
        zipfile=zipfile,
    ))


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    main()
