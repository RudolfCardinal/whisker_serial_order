..  docs/source/installation.rst

..  Copyright © 2016-2018 Rudolf Cardinal (rudolf@pobox.com).
    .
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    .
        http://www.apache.org/licenses/LICENSE-2.0
    .
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

.. _Python: https://www.python.org/


Installation
============

Windows installation from a PyInstaller file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The idea of PyInstaller is that it takes a working Python virtual environment
and packages it up (for that 32- or 64-bit OS and version of Python) so you
don’t have to go through the rigmarole of installing from source
[#pyinstaller_directories]_. So the
installation is quite simple:

- Install MySQL. (The alternative is PostgreSQL; see later.)

    - Browse to http://dev.mysql.com/downloads/installer/ and follow the
      instructions.

    - The web installer works fine here. Choosing the defaults works well, and
      you can add additional users during setup. The default port is 3306, and
      the default superuser account is root.

- Obtain and unzip ``whisker_serial_order_0.3.3_windows.zip``, or equivalent.

- Run ``whisker_serial_order.exe``.

Ubuntu installation from PyPI source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Install MySQL or PostgreSQL. See :ref:`databases`.

- You should have Python_ 3 already (it comes with Ubuntu).

- Create a virtual environment, activate it, and install the Python things. To
  do this, start a shell and enter the following commands:

    .. code-block:: bash

        python3 -m virtualenv ~/venv_whisker_serial_order
        source ~/venv_whisker_serial_order/bin/activate
        pip install whisker_serial_order

The SerialOrder program itself will now be accessible as the command
``whisker_serial_order`` without any PATH modifications as long as you have
activated the virtual environment (the second command above).

After installation
~~~~~~~~~~~~~~~~~~

- Create a database. See :ref:`databases`.

- Compose your database URL. If you create a database named ``serialorder``,
  with a user named ``researcher`` and a password of ``blueberry``, then to use
  the MySQL Connector/Python interface, the URL would be:

  .. code-block:: none

    mysql+mysqlconnector://researcher:blueberry@localhost/serialorder

- Tell SerialOrder about this URL, either via an environment variable or as a
  command-line parameter (see below). The simplest is as a command-line
  parameter, as below.

- Launch SerialOrder:

  .. code-block:: bash

    whisker_serial_order --dburl=your_URL_as_above

- For details of all possible command-line options, use:

  .. code-block:: bash

    whisker_serial_order --help

- The first time you run it, you should get an error like “Database revision
  should be 0003 but is None”. Update the database with:

  .. code-block:: none

	whisker_serial_order --dburl=your_URL_as_above --upgrade-database

  Then re-run.


.. rubric:: Footnotes

.. [#pyinstaller_directories]

A bit of tweaking to the source is required, because things don’t live in the
same directory structure as normal, but this is achievable. To build, you:

    #. check out the Git repository;
    #. create/activate the Python virtual environment;
    #. install (with ``pip install -e .``);
    #. check it runs;
    #. ``pip install pyinstaller``;
    #. run ``tools/make_pyinstaller_distributable.py``.
