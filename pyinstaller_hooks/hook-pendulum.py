#!/usr/bin/env python
# pyinstaller_hooks/hook-pendulum.py

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

Hook to install Pendulum properly. See

- https://github.com/pyinstaller/pyinstaller/issues/3528
- https://pyinstaller.readthedocs.io/en/latest/hooks.html

The error from Pendulum is:

.. code-block:: none

    ...
      File "/home/rudolf/dev/venvs/whisker_serial_order/lib/python3.5/site-packages/PyInstaller/loader/pyimod03_importers.py", line 627, in exec_module
        exec(bytecode, module.__dict__)
      File "site-packages/pendulum/helpers.py", line 29, in <module>
      File "site-packages/pendulum/formatting/difference_formatter.py", line 12, in __init__
      File "site-packages/pendulum/locales/locale.py", line 38, in load
    ValueError: Locale [en] does not exist.
    [14280] Failed to execute script main

The missing file is probably one of:

- ``pendulum/locales/en/custom.py``
- ``pendulum/locales/en/locale.py`` -- this one, I think.

"""  # noqa

import logging
import os
import sys
from typing import Generator, Iterable, Tuple

from PyInstaller.utils.hooks import collect_data_files

log = logging.getLogger(__name__)

def no_pyc(data_files: Iterable[Tuple[str, str]]) \
        -> Generator[Tuple[str, str], None, None]:
    """
    Filter out ``*.pyc`` files.
    """
    for filename, directory in data_files:
        if os.path.splitext(filename)[1] == ".pyc":
            continue
        yield filename, directory


datas = list(no_pyc(collect_data_files("pendulum.locales",
                                       include_py_files=True)))

TEST_HOOK = False
if TEST_HOOK:
    log.critical("Deliberately aborting to test PyInstaller hook")
    log.critical("datas = \n" + "\n".join(repr(x) for x in datas))
    sys.exit(1)
