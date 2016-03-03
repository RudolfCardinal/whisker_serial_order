#!/usr/bin/env python
# whisker_serial_order/constants.py

import os
import string

from .version import VERSION

LINESEP = "=" * 79

# =============================================================================
# Database stuff
# =============================================================================

ALEMBIC_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_CONFIG_FILENAME = 'alembic.ini'
DB_URL_ENV_VAR = "WHISKER_SERIAL_ORDER_DB_URL"
MSG_DB_ENV_VAR_NOT_SPECIFIED = """
{LINESEP}
You must specify the {var} environment variable (which is
an SQLAlchemy database URL), or pass it as a command-line argument. Examples
follow.

Windows:
    set {var}=sqlite:///C:\\path\\to\\database.sqlite3
Linux:
    export {var}=sqlite:////absolute/path/to/database.sqlite3
{LINESEP}
""".format(LINESEP=LINESEP, var=DB_URL_ENV_VAR)
WRONG_DATABASE_VERSION_STUB = string.Template("""
$LINESEP
Database revision should be {head_revision} but is {current_revision}.

- If the database version is too low, run the task with the
  "--upgrade-database" parameter (because your database is too old), or click
  the "Upgrade database" button in the GUI.

- If the database version is too high, upgrade the task (because you're
  trying to use an old task version with a newer database).
$LINESEP
""").substitute(LINESEP=LINESEP)

# =============================================================================
# About
# =============================================================================

ABOUT = """
<b>Serial Order v{VERSION}</b><br>
<br>
Serial order task for Whisker (<a href="{WHISKER_URL}">{WHISKER_URL}</a>).<br>

You will also need:
<ul>
  <li>A database. Any backend supported by SQLAlchemy will do (see
    <a href="{BACKEND_URL}">{BACKEND_URL}</a>).
    SQLite is quick. This task finds its database using the environment
    variable {DB_URL_ENV_VAR}.</li>
  <li>You may want a graphical tool for database management. There are lots.
    For SQLite, consider Sqliteman
    (<a href="{SQLITEMAN_URL}">{SQLITEMAN_URL}</a>).
</ul>

By Rudolf Cardinal (rudolf@pobox.com).<br>
Copyright &copy; 2016 Rudolf Cardinal.
For licensing details see LICENSE.txt.
""".format(
    BACKEND_URL="http://docs.sqlalchemy.org/en/latest/core/engines.html",
    DB_URL_ENV_VAR=DB_URL_ENV_VAR,
    SQLITEMAN_URL="http://sqliteman.yarpen.cz/",
    VERSION=VERSION,
    WHISKER_URL="http://www.whiskercontrol.com/",
)

DATETIME_FORMAT_PRETTY = "%Y-%m-%d %H:%M:%S"
