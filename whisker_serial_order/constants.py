#!/usr/bin/env python
# whisker_serial_order/constants.py

DB_URL_ENV_VAR = "WHISKER_SERIAL_ORDER_DB_URL"

DATABASE_ENV_VAR_NOT_SPECIFIED = """
===============================================================================
You must specify the {var} environment variable (which is an
SQLAlchemy database URL). Examples follow.

Windows:
    set {var}=sqlite:///C:\\path\\to\\database.sqlite3
Linux:
    export {var}=sqlite:////absolute/path/to/database.sqlite3
===============================================================================
""".format(var=DB_URL_ENV_VAR)
