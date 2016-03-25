#!/usr/bin/env python

import os
import shutil
import subprocess
import sys
if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
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
