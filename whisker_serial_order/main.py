#!/usr/bin/env python
# whisker_serial_order/main.py

"""
Serial order task for Whisker.

    Copyright © 2016-2016 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

# =============================================================================
# Imports
# =============================================================================

import argparse
import logging
log = logging.getLogger(__name__)
import os
import sys

import PySide
from whisker.debug_qt import enable_signal_debugging_simply
from whisker.logsupport import (
    configure_logger_for_colour,
    copy_all_logs_to_file,
)
from whisker.qtclient import WhiskerOwner
from whisker.qtsupport import run_gui
from whisker.sqlalchemysupport import (
    get_current_and_head_revision,
    upgrade_database,
)
import whisker.version

# http://stackoverflow.com/questions/16981921/relative-imports-in-python-3
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(
    os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, os.pardir)))
# Now we can import from our own package:

from whisker_serial_order.constants import (
    DATABASE_ENV_VAR_NOT_SPECIFIED,
    DB_URL_ENV_VAR,
)
from whisker_serial_order.gui import (
    MainWindow,
    NoDatabaseSpecifiedWindow,
    WrongDatabaseVersionWindow,
)
from whisker_serial_order.version import VERSION


# =============================================================================
# Main
# =============================================================================

def main():
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="whisker_serial_order v{}. Serial order task for "
        "Whisker.".format(VERSION))
    parser.add_argument("--logfile", default=None,
                        help="Filename to append log to")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('--upgrade-database', action="store_true",
                        help="Upgrade database to current version.")
    parser.add_argument('--debug-qt-signals', action="store_true",
                        help="Debug QT signals.")
    parser.add_argument(
        "--dburl", default=None,
        help="Database URL (if not specified, task will look in {} "
        "environment variable).".format(DB_URL_ENV_VAR))
    parser.add_argument('--gui', '-g', action="store_true",
                        help="GUI mode only")

    # We could allow extra Qt arguments:
    # args, unparsed_args = parser.parse_known_args()
    # Or not:
    args = parser.parse_args()
    unparsed_args = []

    qt_args = sys.argv[:1] + unparsed_args

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    rootlogger.setLevel(loglevel)
    configure_logger_for_colour(rootlogger)  # configure root logger
    if args.logfile:
        copy_all_logs_to_file(args.logfile)

    # -------------------------------------------------------------------------
    # Info
    # -------------------------------------------------------------------------
    log.info("whisker_serial_order v{}: Serial order task for Whisker, "
             "by Rudolf Cardinal (rudolf@pobox.com)".format(VERSION))
    log.debug("args: {}".format(args))
    log.debug("qt_args: {}".format(qt_args))
    log.debug("PySide version: {}".format(PySide.__version__))
    log.debug("QtCore version: {}".format(PySide.QtCore.qVersion()))
    log.debug("Whisker client version: {}".format(whisker.version.VERSION))
    in_bundle = getattr(sys, 'frozen', False)
    if in_bundle:
        args.gui = True
        logger.debug("Running inside a PyInstaller bundle")
    if args.gui:
        logger.debug("Running in GUI-only mode")
    if args.debug_qt_signals:
        enable_signal_debugging_simply()

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    # Get URL, or complain
    database_url = args.dburl or os.getenv(DB_URL_ENV_VAR)
    if not database_url:
        if args.gui:
            return run_gui(NoDatabaseSpecifiedWindow(), qt_args)
        raise ValueError(DATABASE_ENV_VAR_NOT_SPECIFIED)
    log.debug("Using database URL: {}".format(database_url))
    dbsettings = {
        'url': database_url,
        # 'echo': True,
        'echo': False,
        'connect_args': {
            # 'timeout': 15,
        },
    }
    alembic_config_filename = 'alembic.ini'
    alembic_base_dir = SCRIPT_DIR

    # Has the user requested a command-line database upgrade?
    if args.upgrade_database:
        sys.exit(upgrade_database(alembic_config_filename, alembic_base_dir))
    # Is the database at the correct version?
    (current_revision, head_revision) = get_current_and_head_revision(
        database_url, alembic_config_filename, alembic_base_dir)
    if current_revision != head_revision:
        if args.gui:
            return run_gui(
                WrongDatabaseVersionWindow(current_revision, head_revision),
                qt_args
            )
        raise ValueError(WRONG_DATABASE_VERSION_STUB.format(
            head_revision=head_revision,
            current_revision=current_revision))

    # -------------------------------------------------------------------------
    # Run app
    # -------------------------------------------------------------------------
    return run_gui(MainWindow(), qt_args)


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    sys.exit(main())
