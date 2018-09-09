#!/usr/bin/env python
# whisker_serial_order/docs/rebuild_docs.py

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

import os
import shutil
import subprocess
import sys
if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")


_OLD_METHOD = r"""

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # whisker_serial_order/tools  # noqa
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))  # whisker_serial_order  # noqa
DOC_DIR = os.path.join(PROJECT_BASE_DIR, 'whisker_serial_order')
DEST_DIR = DOC_DIR

ODT = os.path.join(DOC_DIR, 'MANUAL.odt')
PDF = os.path.join(DEST_DIR, 'MANUAL.pdf')

LIBREOFFICE = shutil.which('soffice')

if __name__ == '__main__':
    os.makedirs(DEST_DIR, exist_ok=True)
    print("Converting {} -> {}".format(ODT, PDF))
    args = [
        LIBREOFFICE,
        '--convert-to', 'pdf:writer_pdf_Export',
        '--outdir', DEST_DIR,
        ODT
    ]
    print(args)
    subprocess.check_call(args)  # doesn't appear to set errorlevel on failure!
    print("Success? Not sure; LibreOffice doesn't say. Check the PDF date.")

"""

# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
BUILD_HTML_DIR = os.path.join(THIS_DIR, "build", "html")

DEST_DIRS = []

if __name__ == '__main__':
    # Remove anything old
    for destdir in [BUILD_HTML_DIR] + DEST_DIRS:
        print("Deleting directory {!r}".format(destdir))
        shutil.rmtree(destdir, ignore_errors=True)

    # Build docs
    print("Making HTML version of documentation")
    os.chdir(THIS_DIR)
    subprocess.call(["make", "html"])

    # Copy
    for destdir in DEST_DIRS:
        print("Copying {!r} -> {!r}".format(BUILD_HTML_DIR, destdir))
        shutil.copytree(BUILD_HTML_DIR, destdir)
