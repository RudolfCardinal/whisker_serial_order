..  whisker_serial_order/docs/source/development_notes.rst

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


.. _Arrow: https://arrow.readthedocs.io/en/latest/
.. _Pendulum: https://pendulum.eustace.io/
.. _SQLAlchemy-Utils: https://sqlalchemy-utils.readthedocs.io/en/latest/

Development notes
=================

.. _dev_date_time:

Dates and times
---------------

As discussed earlier, the end user is probably best off with a native format
that supports microsecond-accuracy precision, such as the ``DATETIME(fsp)``,
e.g. ``DATETIME(6)``, format available in MySQL 5.6.4 and higher
[#mysqldatetime]_. There are others [#sqladatabases]_, notably PostgreSQL,
which uses a ``TIMESTAMP`` format that has microsecond precision. You’d think
it can store time zones as well (``TIMESTAMP WITH TIME ZONE``), but close
inspection shows that “For TIMESTAMP WITH TIME ZONE, the internally stored
value is always in UTC... [a]n input value that has an explicit time zone is
converted to UTC...” [#postgrestimestamp]_. In other words, there’s not much to
choose between PostgreSQL and MySQL on the basis of date/time handling.

Interestingly, on the commercial side, SQL Server 2008+ provides
``DATETIMEOFFSET``, which preserves timezone information [#sqlserverdatetimeoffset]_, and Oracle has a version
of ``TIMESTAMP WITH TIME ZONE`` that can preserve timezone information [#oracledatetime]_. Neither
PostgreSQL or MySQL appear to have an equivalent; the best they offer is UTC
high-precision storage (and you could store the timezone of origin separately,
e.g. with the ``TimezoneType`` from SQLAlchemy-Utils_). I haven’t managed to
get ``TimezoneType`` working cleanly, in that (a) I’m unsure of the best
general way to get the current timezone using either ``pytz`` or
``dateutil.tz.tzlocal()``; (b) Alembic adds a ``length=50`` argument to the
constructor, which is wrong and requires manual removal. Anyway, it’s not too
important here.

For general advice, see also [#generaldatetimeadvice]_.

The best Python module was Arrow_, which offers ``arrow.now()`` to get a
timezone-aware, microsecond-precision object in the local timezone. More
recently, Pendulum_ looks better.

There is an ``ArrowType`` for SQLAlchemy in SQLAlchemy-Utils
[#sqlalchemyutilsdatatypes]_; however, this converts to UTC as it sends to the
database (and UTC ``Arrow`` objects back out again), so the source timezone is
lost. But this is actually normal PostgreSQL behaviour, as above, which always
uses UTC internally. An alternative (as per CamCOPS) is to use ISO-8601
strings, but they’re much less convenient for end user comparison. So, the best
bet is to use ``Arrow``, ``ArrowType``, and accept that everything in the
database is in UTC. This works fine for PostgreSQL, where the default
``TIMESTAMP`` has microsecond precision. **However,** by default the
``ArrowType`` uses a plain ``DATETIME`` in MySQL, which has only second
precision; we need ``DATETIME(6)``. We therefore require not only MySQL 5.6.4+
but a custom ``ArrowMicrosecondType``. Duly added. For SQL Server, this class
uses ``DATETIME2``, available from SQL Server 2008+ [#sqlserverdatetime2]_.

To summarize, **in this task, all timestamps are in UTC.**


Where to store BLOBs
--------------------

Completely irrelevant here, but see
https://wiki.postgresql.org/wiki/BinaryFilesInDB.


Primary key naming convention
-----------------------------

Primary keys as ‘id’ or ‘trial_id’? There’s no right answer [#pknaming]_.
However, here we are aiming for simplicity of use for database novices. Using
``SELECT a.something, b.*`` statements may be common, at which point when a
column labelled ‘id’ pops up, people may be unclear as to what it is. So for
this particular scenario, we will use the ‘table.table_id’ convention.

For queries, duplicate column names don’t matter (and if their values don’t
match, that’s an important clue to query failure!). For views, duplicates do
matter, but views should be more carefully constructed anyway.



Strings
-------

The SQLAlchemy ``String()`` type can be of variable length in PostgreSQL and
SQLite, but needs a length in MySQL. The SQLAlchemy ``Text()`` is always of
variable length.

Avoid ``TEXT`` columns for things that have a realistic maximum length, as you
can’t use ``TEXT`` columns for primary keys (e.g. for ‘subject’ tables that
cross-refer).



Trial maths
-----------

*Definitions.*

The number of :math:`k`-permutations from :math:`n` objects:

.. math::

    P(n, k) = n! / (n – k)!

..  See
    http://anorien.csc.warwick.ac.uk/mirrors/CTAN/info/short-math-guide/short-math-guide.pdf
    https://www.sharelatex.com/learn/Spacing_in_math_mode

The number of :math:`k`-combinations from :math:`n` objects:

.. math::

    C(n, k) = n! / [(n – k)! k!]

In our situation, we always offer two choices and have five holes available;
this gives :math:`C(5, 2) = 10` possible spatial choices. For a stimulus
sequence of length :math:`l`, the number of sequences is :math:`P(5, l)`. The
spatial choice is not independent of the sequence (e.g. if you present lights
3-1-4 you can’t then offer a choice of 2-5). The serial order choice is
independent of the sequence, and there are :math:`C(l, 2)` of these, as
follows:

..  No maths inside italics.

.. list-table::
    :header-rows: 1

    * - Sequence length :math:`l`
      - Number of possible sequences, :math:`P(5, l)`
      - Number of serial order choices, :math:`C(l, 2)`
      - [Less relevant!] Number of spatial choices, :math:`C(5, 2)`; not all
        available on any given trial
      - Maximum number of independent trial types, :math:`P(5, l)C(l, 2)`

    * - *Example: presenting holes 3-1-4 is a sequence of length 3.*
      - *Example: with five holes, sequences of length 3 include 1-2-3, 1-2-5,
        3-2-1.*
      - *Example: if you presented sequence 3-1-4, then the serial order
        choices are "1 or 3?", "1 or 4?", "3 or 4?".*
      - *With five holes, the choices could be presented in holes 1+2, 1+3,
        ..., 4+5, though not all are possible on a given trial.*
      - For each of the :math:`P(5, l)` possible sequences, you can offer
        :math:`C(l, 2)` serial order choices.

    * - 2
      - 20
      - 1
      - 10
      - 20

    * - 3
      - 60
      - 3
      - 10
      - 180

    * - 4
      - 120
      - 6
      - 10
      - 720

    * - 5
      - 120
      - 10
      - 10
      - 1200


In general, since this task is about serial order detection, *serial order
choices are the most important* and should vary most rapidly (e.g. for :math:`l
= 4`, every 6 trials should cover all of the 6 possible serial order choices,
in random order). Next most important is spatial choice (it’s of some
importance that choices are equally distributed spatially); **note** that the
number of spatial choices is not always a multiple of the number of serial
order choices. Last comes sequence (it’s least important that all possible
sequences are presented). But there is no obviously consistent way of
randomizing in groups across all three (since some of them are interdependent
and they are not necessarily multiples of each other), so I think the best
approach is to randomize across sequences, which should give a nice spatial
spread (through randomness alone), in addition to the guarantees about serial
order sampling.

Therefore our algorithm will be:

- For each stage, we establish the possible serial order choices, and the
  possible sequences. We combine them into all possible combinations.

- We then shuffle them in blocks, such that *serial order is randomized in
  blocks with the highest rate of change*, so that in every :math:`C(l, 2)`
  trials there are all possible serial orders.

- Since that gives a rather dull and static stimulus sequence, we then
  randomize the sequences. So sequences vary randomly but the serial order
  sampling is in blocks.

- We then sample in order from our ‘hat’. If we run out, we repopulate the hat,
  as above.


Progression maths
-----------------

If we progress when :math:`x` of the last :math:`y` trials are performed
correctly, then we should have some sense that this isn’t going to happen by
chance. In R, use ``binom.test(x, y)`` to get the *p*-value based on the
assumption of *P* = 0.5 for chance (and it is, after all, a two-choice test).
The default values are 10 out of 12, for *p* = 0.03857.

Trials can also be failed by not responding, affecting the “ignorance ⇒ *P* =
0.5” assumption, but in a conservative way.


Alternative installation methods that can fail
----------------------------------------------

CAN WORK, CAN FAIL: Windows installation from PyPI source: Python 3.4
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Don’t use Windows XP; it’s too old for MySQL. The following has been tested on
Windows 10.

• Install Visual C++ Redistributable Packages for Visual Studio 2013, which
  you’ll want in order to get MySQL Workbench installed.

  - Get this from https://www.microsoft.com/en-GB/download/details.aspx?id=40784.

- Install Python 3.4, which by default will be installed to ``C:\Python34\``.

  - Explore from https://www.python.org/, or go direct to
    https://www.python.org/downloads/release/python-344/.

- Install MySQL. (The alternative is PostgreSQL; see later.)

  - Browse to http://dev.mysql.com/downloads/installer/ and follow the
    instructions.

  - The web installer works fine here. Choosing the defaults works well, and
    you can add additional users during setup. The default port is 3306, and
    the default superuser account is ``root``.

- Download a binary version of PySide 1.2.2, since source code versions have
  all sorts of tricky compiler requirements.

  - Download ``PySide-1.2.2-cp34-none-win_amd64.whl`` or
    ``PySide-1.2.2-cp34-none-win32.whl`` from
    http://www.lfd.uci.edu/~gohlke/pythonlibs/#pyside. Remember where you
    stored it.

- Create and activate a virtual environment. Upgrade the installation tools
  (may be unnecessary, but confusing errors appear if it was, in fact,
  necessary). Install PySide and MySQL Connector/Python, then
  whisker_serial_order.

  - Start a command prompt (:menuselection:`Start --> Command Prompt`) and type
    the following.

    .. code-block:: bat

        C:\Python34\python.exe -m ensurepip
        C:\Python34\python.exe -m pip install --upgrade pip
        C:\Python34\python.exe -m pip install --upgrade virtualenv
        C:\Python34\python.exe -m virtualenv C:\venv_whisker_serial_order

        REM Activate the virtual environment:
        C:\venv_whisker_serial_order\Scripts\activate.bat

        pip install https://cdn.mysql.com/Downloads/Connector-Python/mysql-connector-python-2.1.3.tar.gz

        REM Change the filename that follows if you are using the 32-bit
        REM version; add a path if you stored it somewhere other than the
        REM current directory).
        pip install PySide-1.2.2-cp34-none-win_amd64.whl

        pip install whisker_serial_order

  - If anything fails to build, download the corresponding binary from
    http://www.lfd.uci.edu/~gohlke/pythonlibs/, install it as above, and repeat
    ``pip install whisker_serial_order``. Nothing else was required on the test
    machine. But others (with 64-bit Windows 7) had problems with other
    packages not compiling.

The SerialOrder program itself will now be accessible as the command
``whisker_serial_order`` without any PATH modifications as long as you have
activated the virtual environment (see activation command in bold above).


FAILED: Installation from a Python binary wheel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The idea here is that you have a development computer that can compile anything
necessary, i.e. with (a) Python 3.4, (b) MSVC 10.0 (such as from Visual C++
2010 Express) [#vc2010express]_, and (c) CMake (https://cmake.org/) installed
to the PATH (or: ``set PATH=%PATH%;“C:\Program Files (x86)\CMake\bin”``). Then
to build, you (1) run the Visual Studio Command Prompt (2010) to set up
appropriate environment variables; (2) activate your Python virtual
environment; run ``pip wheel whisker_serial_order``. However, at present this
complains that it can’t find ``cmake``, even when ``cmake`` is on the path
(whilst running ``setup bdist_wheel`` for PySide). So perhaps PySide doesn’t
live happily with this.


NOT YET POSSIBLE: Windows installation from PyPI source: Python 3.5
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Install Microsoft Visual Studio Community 2015, from
  https://www.visualstudio.com/en-us/products/visual-studio-community-vs.aspx
  [#vscommunity2015]_.

- Install Python 3.5 (e.g. 3.5.0) from https://www.python.org/. Simplest is to
  use the x86-64 (64-bit) or x86 (32-bit) web installer. Change the install
  location to ``C:\Python35\`` for simplicity (or change the path references
  below accordingly).

- Create and activate a virtual environment. Upgrade the installation tools.
  Install MySQL Connector/Python, plus whisker_serial_order and its
  dependencies.

  - Start a command prompt (:menuselection:`Start --> Command Prompt`) and type
    the following.

    .. code-block:: bat

        C:\Python35\python -m ensurepip
        C:\Python35\python -m pip install --upgrade pip
        C:\Python35\python -m pip install --upgrade virtualenv
        C:\Python35\python -m virtualenv C:\venv_whisker_serial_order
        C:\venv_whisker_serial_order\Scripts\activate.bat
        pip install https://cdn.mysql.com/Downloads/Connector-Python/mysql-connector-python-2.1.3.tar.gz
        pip install whisker_serial_order

- However, the ``pip install whisker_serial_order`` step fails because PySide
  1.2.4 explicitly doesn’t yet support Python 3.5 (as of 2015-03-22), and
  PySide 1.2.2 just fails to install.


PyInstaller complications
-------------------------

If you use ``EXE(console=True)``, Python logging output goes to the console
window (good). But if the user closes the console, the child GUI process dies
instantly without asking for confirmation (very bad). If you use
``EXE(console=False)``, there is good protection against user error, because
you can trap exit requests (very good), but if an error occurs that is not
reported by the GUI – such as a database connection error causing a Python
exception – you see nothing, which is very confusing (bad).

What would be ideal is the ability to set ``console=True`` (or equivalent) but
prevent the parent console from being closed.

Or to have the primary process being GUI (``console=False`` and perhaps the
``launch_no_console.pyw`` script as per Starfeeder), but have a child
console [#childconsole]_...

.. todo:: GUI/console problem could be improved.


.. rubric:: Footnotes

.. [#mysqldatetime]

    http://dev.mysql.com/doc/refman/5.7/en/datetime.html

.. [#sqladatabases]

    http://docs.sqlalchemy.org/en/latest/core/engines.html#supported-databases

.. [#postgrestimestamp]

    http://www.postgresql.org/docs/9.1/static/datatype-datetime.html

.. [#sqlserverdatetimeoffset]

    https://msdn.microsoft.com/en-us/library/bb630289.aspx;
    https://blogs.msdn.microsoft.com/bartd/2009/03/31/the-death-of-datetime/

.. [#oracledatetime]

    https://docs.oracle.com/cd/B19306_01/server.102/b14225/ch4datetime.htm#i1006081;
    but see
    https://tonyhasler.wordpress.com/2010/09/04/tonys-tirade-against-timestamp-with-time-zone/

.. [#generaldatetimeadvice]

    http://stackoverflow.com/questions/1646171/mysql-datetime-fields-and-daylight-savings-time-how-do-i-reference-the-extra;
    and especially
    http://stackoverflow.com/questions/2532729/daylight-saving-time-and-time-zone-best-practices

.. [#sqlalchemyutilsdatatypes]

    http://sqlalchemy-utils.readthedocs.org/en/latest/data_types.html

.. [#sqlserverdatetime2]

    https://blogs.msdn.microsoft.com/cdnsoldevs/2011/06/22/why-you-should-never-use-datetime-again/;
    http://stackoverflow.com/questions/1334143/sql-server-datetime2-vs-datetime

.. [#pknaming]

    http://programmers.stackexchange.com/questions/114728;
    http://stackoverflow.com/questions/1369593

.. [#vc2010express]

    https://go.microsoft.com/?linkid=9709969

.. [#vscommunity2015]

    Visual Studio 2015 is the standard C/C++ compiler for Python 3.5
    under Windows (https://docs.python.org/3/using/windows.html). A compiler is
    needed to install and build third-party tools from source where those tools
    include C components.

.. [#childconsole]

    http://stackoverflow.com/questions/24469662/how-to-redirect-logger-output-into-pyqt-text-widget;
    http://stackoverflow.com/questions/11465971/redirecting-output-in-pyqt;
    http://stackoverflow.com/questions/8356336/how-to-capture-output-of-pythons-interpreter-and-show-in-a-text-widget
