#!/usr/bin/env python
# whisker_serial_order/task.py

import logging
log = logging.getLogger(__name__)

from PySide.QtCore import Signal
from whisker.constants import (
    CMD_CLAIM_GROUP,
    CMD_LINE_CLAIM,
    CMD_REPORT_NAME,
    FLAG_INPUT,
    FLAG_OUTPUT,
)
from whisker.exceptions import WhiskerCommandFailed
from whisker.qtclient import WhiskerTask
from whisker.qtsupport import exit_on_exception
from whisker.sqlalchemysupport import get_database_session_thread_scope

from .models import Config
from .version import VERSION

# =============================================================================
# Whisker devices (DI = digital in; DO = digital out)
# =============================================================================
# see http://www.whiskercontrol.com/help/FiveChoice.pdf

N_HOLES = 5

DEV_DI_HOLES = ["HOLE_{}".format(h) for h in range(0, N_HOLES)]

DEV_DO_HOUSELIGHT = "HOUSELIGHT"
DEV_DO_PELLET = "PELLET"
DEV_DO_TRAYLIGHT = "TRAYLIGHT"
DEV_DO_STIMLIGHTS = ["STIMLIGHT_{}".format(h) for h in range(0, N_HOLES)]

ALL_INPUTS = DEV_DI_HOLES
ALL_OUTPUTS = [
    DEV_DO_HOUSELIGHT,
    DEV_DO_PELLET,
    DEV_DO_TRAYLIGHT,
] + DEV_DO_STIMLIGHTS

# =============================================================================
# Events
# =============================================================================


# =============================================================================
# Task
# =============================================================================

class SerialOrderTask(WhiskerTask):
    task_status_sig = Signal(str, str, str)

    # -------------------------------------------------------------------------
    # Creation, thread startup, shutdown.
    # -------------------------------------------------------------------------

    def __init__(self, dbsettings, config_id):
        super().__init__()
        self.dbsettings = dbsettings
        self.config_id = config_id
        # DO NOT CREATE SESSION OBJECTS HERE - WRONG THREAD.
        # Create them in thread_started().
        self.session = None
        self.config = None

    def thread_started(self):
        log.debug("thread_started")
        self.session = get_database_session_thread_scope(self.dbsettings)
        # ... keep the session running, if we can; simpler
        self.config = self.session.query(Config).get(self.config_id)

    def stop(self):
        self.session.commit()
        self.session.close()
        super().stop()

    # -------------------------------------------------------------------------
    # Shortcuts
    # -------------------------------------------------------------------------

    def cmd(self, *args):
        self.whisker.command_exc(*args)

    def report(self, msg1='', msg2='', msg3=''):
        self.task_status_sig.emit(msg1, msg2, msg3)

    # -------------------------------------------------------------------------
    # Connection and startup
    # -------------------------------------------------------------------------

    @exit_on_exception
    def on_connect(self):
        log.info("SerialOrderTask: on_connect")
        self.whisker.command(CMD_REPORT_NAME, "SerialOrder", VERSION)
        try:
            self.claim()
        except WhiskerCommandFailed as e:
            log.critical(
                "Command failed: {}".format(e.args[0] if e.args else '?'))
        self.start_task()

    def claim(self):
        log.info("Claiming devices...")
        self.cmd(CMD_CLAIM_GROUP, self.config.devicegroup)
        for d in ALL_INPUTS:
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_INPUT)
        for d in ALL_OUTPUTS:
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_OUTPUT)
        log.info("... devices successfully claimed")

    def start_task(self):
        log.info("*** START TASK ***")
        self.report("Started.")
        self.whisker.flash_line_pulses(DEV_DO_HOUSELIGHT, count=5,
                                       on_ms=1000, off_ms=50, on_at_rest=False)

    # -------------------------------------------------------------------------
    # Event processing
    # -------------------------------------------------------------------------

    @exit_on_exception  # @Slot(str, datetime.datetime, int)
    def on_event(self, event, timestamp, whisker_timestamp_ms):
        log.info("SerialOrderTask: on_event: {}".format(event))
        # ***
