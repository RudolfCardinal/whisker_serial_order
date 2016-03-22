#!/usr/bin/env python

import os
import platform
import shutil
import subprocess
import sys

from whisker_serial_order.version import VERSION

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
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
BUILD_DIR = os.path.join(PROJECT_BASE_DIR, 'build')
DIST_DIR = os.path.join(PROJECT_BASE_DIR, 'dist')
DIST_SUBDIR = os.path.join(DIST_DIR, 'whisker_serial_order')
LAUNCHFILE = os.path.join(DIST_SUBDIR, 'whisker_serial_order')

SPECFILE = os.path.join(PROJECT_BASE_DIR, 'whisker_serial_order.spec')
WARNFILE = os.path.join(BUILD_DIR, 'whisker_serial_order',
                        'warn_whisker_serial_order.txt')
ZIPFILEBASE = os.path.join(
    DIST_DIR,
    'whisker_serial_order_{VERSION}_{PLATFORM}'.format(
        VERSION=VERSION,
        PLATFORM=PLATFORM,
        ZIPEXT=ZIPEXT,
    )
)

SEP = "=" * 79


def title(msg):
    print(SEP)
    print(msg)
    print(SEP)


def main():
    title("Deleting old distribution...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    title("Building new distribution...")
    subprocess.check_call(
        ['pyinstaller', '--clean', '--log-level=INFO']
        + PYINSTALLER_EXTRA_OPTIONS
        + [SPECFILE]
    )

    title("Zipping to {}...".format(ZIPFILEBASE))
    zipfile = shutil.make_archive(ZIPFILEBASE, ZIPFORMAT, DIST_SUBDIR)

    print("""
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
    main()
