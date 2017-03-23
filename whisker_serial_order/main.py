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
import os
import random
import subprocess
import sys
import traceback

from PyQt5.Qt import PYQT_VERSION_STR
from PyQt5.QtCore import QT_VERSION_STR
from PyQt5.QtWidgets import QApplication
import sadisplay
# from whisker.debug_qt import enable_signal_debugging_simply
from whisker.logging import (
    configure_logger_for_colour,
    copy_root_log_to_file,
)
from whisker.qt import (
    LogWindow,
    run_gui,
)
from whisker.sqlalchemy import (
    database_is_sqlite,
    get_current_and_head_revision,
    upgrade_database,
)
import whisker.version

from whisker_serial_order.constants import (
    ALEMBIC_BASE_DIR,
    ALEMBIC_CONFIG_FILENAME,
    DB_URL_ENV_VAR,
    MSG_DB_ENV_VAR_NOT_SPECIFIED,
    OUTPUT_DIR_ENV_VAR,
    WRONG_DATABASE_VERSION_STUB,
)
from whisker_serial_order.gui import (
    MainWindow,
    NoDatabaseSpecifiedWindow,
    WINDOW_TITLE,
    WrongDatabaseVersionWindow,
)
import whisker_serial_order.models as models
from whisker_serial_order.settings import (
    dbsettings,
    get_output_directory,
    set_database_echo,
    set_database_url,
    set_output_directory,
)
from whisker_serial_order.task import SerialOrderTask
from whisker_serial_order.version import VERSION

log = logging.getLogger(__name__)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="whisker_serial_order v{}. Serial order task for "
        "Whisker.".format(VERSION))
    parser.add_argument("--logfile", default=None,
                        help="Filename to append log to")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose. (Use twice for extra verbosity.)")
    parser.add_argument('--guilog', action="store_true",
                        help="Show Python log in a GUI window")
    parser.add_argument('--upgrade-database', action="store_true",
                        help="Upgrade database to current version.")
    # parser.add_argument('--debug-qt-signals', action="store_true",
    #                     help="Debug QT signals.")
    parser.add_argument(
        "--dburl", default=None,
        help="Database URL (if not specified, task will look in {} "
        "environment variable).".format(DB_URL_ENV_VAR))
    parser.add_argument('--dbecho', action="store_true",
                        help="Echo SQL to log.")
    parser.add_argument(
        "--outdir", default=None,
        help="Directory for output file (if not specified, task will look in "
        "{} environment variable, or if none, working directory).".format(
            OUTPUT_DIR_ENV_VAR))
    parser.add_argument('--gui', '-g', action="store_true",
                        help="GUI mode only")
    parser.add_argument('--schema', action="store_true",
                        help="Generate schema picture and stop")
    parser.add_argument(
        "--java", default='java',
        help="Java executable (for schema diagrams); default is 'java'")
    parser.add_argument(
        "--plantuml", default='plantuml.jar',
        help="PlantUML Java .jar file (for schema diagrams); default "
        "is 'plantuml.jar'")
    parser.add_argument(
        "--schemastem", default='schema',
        help="Stem for output filenames (for schema diagrams); default is "
        "'schema'; '.plantuml' and '.png' are appended")
    parser.add_argument(
        "--testtrialplan", metavar='SEQUENCE_LEN', type=int, default=None,
        help="Print a test trial plan of the specified sequence length")

    # We could allow extra Qt arguments:
    # args, unparsed_args = parser.parse_known_args()
    # Or not:
    args = parser.parse_args()
    unparsed_args = []

    qt_args = sys.argv[:1] + unparsed_args

    # -------------------------------------------------------------------------
    # Modify settings if we're in a PyInstaller bundle
    # -------------------------------------------------------------------------
    in_bundle = getattr(sys, 'frozen', False)
    if in_bundle:
        args.gui = True
    if not args.gui:
        args.guilog = False

    # -------------------------------------------------------------------------
    # Create QApplication before we create any windows (or Qt will crash)
    # -------------------------------------------------------------------------
    qt_app = QApplication(qt_args)

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    rootlogger = logging.getLogger()
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger.setLevel(loglevel)
    configure_logger_for_colour(rootlogger)  # configure root logger
    logging.getLogger('whisker').setLevel(logging.DEBUG if args.verbose >= 2
                                          else logging.INFO)
    if args.logfile:
        copy_root_log_to_file(args.logfile)
    if args.guilog:
        log_window = LogWindow(level=loglevel,
                               window_title=WINDOW_TITLE + " Python log",
                               logger=rootlogger)
        log_window.show()

    # If any exceptions happen up to this point, we're a bit stuffed.
    # But from now on, we can trap anything and see it in the GUI log, if
    # enabled, even if we have no console.

    # noinspection PyBroadException
    try:

        # ---------------------------------------------------------------------
        # Info
        # ---------------------------------------------------------------------
        log.info("whisker_serial_order v{}: Serial order task for Whisker, "
                 "by Rudolf Cardinal (rudolf@pobox.com)".format(VERSION))
        log.debug("args: {}".format(args))
        log.debug("qt_args: {}".format(qt_args))
        log.debug("PyQt version: {}".format(PYQT_VERSION_STR))
        log.debug("QtCore version: {}".format(QT_VERSION_STR))
        log.debug("Whisker client version: {}".format(whisker.version.VERSION))
        if in_bundle:
            log.debug("Running inside a PyInstaller bundle")
        if args.gui:
            log.debug("Running in GUI-only mode")
        # if args.debug_qt_signals:
        #     enable_signal_debugging_simply()

        # ---------------------------------------------------------------------
        # Schema diagram generation only?
        # ---------------------------------------------------------------------
        if args.schema:
            umlfilename = args.schemastem + '.plantuml'
            log.info("Making schema PlantUML: {}".format(umlfilename))
            desc = sadisplay.describe([
                getattr(models, attr) for attr in dir(models)
            ])
            log.debug(desc)
            with open(umlfilename, 'w') as f:
                f.write(sadisplay.plantuml(desc))
            log.info("Making schema PNG: {}".format(args.schemastem + '.png'))
            cmd = [args.java, '-jar', args.plantuml, umlfilename]
            log.debug(cmd)
            subprocess.check_call(cmd)
            sys.exit(0)

        # ---------------------------------------------------------------------
        # Demo trial plan only?
        # ---------------------------------------------------------------------
        if args.testtrialplan:
            task = SerialOrderTask(dbsettings={}, config_id=-1)
            tplist = task.create_trial_plans(args.testtrialplan)
            print("""
Explanation:
- there are 5 holes, numbered 1-5
- sequence: the sequence of hole numbers presented in the trial
    e.g. for a sequence length of 3, you might have sequence=(3, 1, 4),
    meaning that the subject will be shown hole 3, then hole 1, then hole 4,
    in the first phase
- hole_choice: the two holes presented during the choice phase
    e.g. hole_choice=[3,4]
- serial_order_choice: the serial order, in the first phase, of the two holes
    offered in the second (choice) phase -- in this example, you would get
    serial_order_choice=[1,3], because hole 3 was offered in the choice phase
    and was in position 1 in the sequence, and hole 4 was offered in the
    choice phase and was in position 3 in the sequence.
Hint: use grep to check the output.
            """)
            for i, tp in enumerate(tplist):
                print("{}. {}".format(i, tp))
            sys.exit(0)

        # ---------------------------------------------------------------------
        # File output
        # ---------------------------------------------------------------------
        if args.outdir:
            set_output_directory(args.outdir)
        log.info("Using output directory: {}".format(get_output_directory()))
        if not os.access(get_output_directory(), os.W_OK):
            raise ValueError("Cannot write to output directory")

        # ---------------------------------------------------------------------
        # Database
        # ---------------------------------------------------------------------
        # Get URL, or complain
        if args.dburl:
            set_database_url(args.dburl)
        if args.dbecho:
            set_database_echo(args.dbecho)
        if not dbsettings['url']:
            if args.gui:
                win = NoDatabaseSpecifiedWindow()
                if args.guilog:
                    # noinspection PyUnboundLocalVariable
                    win.exit_kill_log.connect(log_window.exit)
                return run_gui(qt_app, win)
            raise ValueError(MSG_DB_ENV_VAR_NOT_SPECIFIED)
        log.debug("Using database URL: {}".format(dbsettings['url']))
        if database_is_sqlite(dbsettings):
            log.critical(
                "Avoid SQLite: not safe for concurrent use in this context")
            sys.exit(1)

        # Has the user requested a command-line database upgrade?
        if args.upgrade_database:
            sys.exit(upgrade_database(ALEMBIC_CONFIG_FILENAME,
                                      ALEMBIC_BASE_DIR))
        # Is the database at the correct version?
        (current_revision, head_revision) = get_current_and_head_revision(
            dbsettings['url'], ALEMBIC_CONFIG_FILENAME, ALEMBIC_BASE_DIR)
        if current_revision != head_revision:
            if args.gui:
                win = WrongDatabaseVersionWindow(current_revision,
                                                 head_revision)
                if args.guilog:
                    # noinspection PyUnboundLocalVariable
                    win.exit_kill_log.connect(log_window.exit)
                return run_gui(qt_app, win)
            raise ValueError(WRONG_DATABASE_VERSION_STUB.format(
                head_revision=head_revision,
                current_revision=current_revision))

        # ---------------------------------------------------------------------
        # Run app
        # ---------------------------------------------------------------------
        log.debug("Seeding random number generator")
        random.seed()
        win = MainWindow(dbsettings)
        if args.guilog:
            # noinspection PyUnboundLocalVariable
            win.exit_kill_log.connect(log_window.exit)
        return run_gui(qt_app, win)

    except:
        if args.guilog:
            log.critical(traceback.format_exc())
            log_window.set_may_close(True)
            return qt_app.exec_()
        else:
            raise


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    # noinspection PyBroadException
    try:
        sys.exit(main())
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
