#!/usr/bin/env python
# whisker_serial_order/task.py

from enum import Enum, unique
import itertools
import logging
log = logging.getLogger(__name__)
import operator

import arrow
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

from .constants import (
    ALL_HOLE_NUMS,
    DEV_DI,
    DEV_DO,
    TEV,
    WEV,
)
from .models import (
    Config,
    Session,
    Trial,
    Event,
    TrialPlan,
)
from .version import VERSION


# =============================================================================
# Constants
# =============================================================================

@unique
class TaskState(Enum):
    not_started = 0
    awaiting_initiation = 1
    presenting_light = 2
    awaiting_foodmag_after_light = 3
    presenting_choice = 4
    reinforcing = 5
    iti = 6
    finished = 7


# =============================================================================
# Helper functions
# =============================================================================

def get_hole_line(h):
    return DEV_DI["HOLE_{}".format(h)]


def get_stimlight_line(h):
    return DEV_DO["STIMLIGHT_{}".format(h)]


def get_response_hole_from_event(ev):
    """Returns a hole number, or None if it's not a matching event."""
    for h in ALL_HOLE_NUMS:
        if ev == WEV.get('RESPONSE_{}'.format(h), None):
            return h
    return None


# =============================================================================
# Task
# =============================================================================

class SerialOrderTask(WhiskerTask):
    task_status_sig = Signal(str)

    # -------------------------------------------------------------------------
    # Creation, thread startup, shutdown.
    # -------------------------------------------------------------------------

    def __init__(self, dbsettings, config_id):
        super().__init__()
        self.dbsettings = dbsettings
        self.config_id = config_id
        # DO NOT CREATE SESSION OBJECTS HERE - WRONG THREAD.
        # Create them in thread_started().
        self.dbsession = None
        self.config = None
        self.tasksession = None  # current session (only ever one)
        self.trial = None  # current trial
        self.stage = None  # current stage config
        self.eventnum_in_session = 0
        self.eventnum_in_trial = 0
        self.stagenum = 0
        self.state = TaskState.not_started

    def thread_started(self):
        log.debug("thread_started")
        self.dbsession = get_database_session_thread_scope(self.dbsettings)
        # ... keep the session running, if we can; simpler
        self.config = self.dbsession.query(Config).get(self.config_id)

    def stop(self):
        self.dbsession.commit()
        self.dbsession.close()
        super().stop()

    # -------------------------------------------------------------------------
    # Shortcuts
    # -------------------------------------------------------------------------

    def cmd(self, *args):
        self.whisker.command_exc(*args)

    def timer(self, *args):
        self.whisker.timer_set_event(*args)

    def cancel_timer(self, event):
        self.whisker.timer_clear_event(event)

    def report(self, msg):
        self.task_status_sig.emit(msg)

    def record_event(self, event, timestamp=None, whisker_timestamp_ms=None,
                     from_server=False):
        if timestamp is None:
            timestamp = arrow.now()
        self.eventnum_in_session += 1
        if self.trial:
            trial_id = self.trial.id
            trialnum = self.trial.trialnum
            self.eventnum_in_trial += 1
            eventnum_in_trial = self.eventnum_in_trial
        else:
            trial_id = None
            trialnum = None
            eventnum_in_trial = None
        eventobj = Event(eventnum_in_session=self.eventnum_in_session,
                         trial_id=trial_id,
                         trialnum=trialnum,
                         eventnum_in_trial=eventnum_in_trial,
                         event=event,
                         timestamp=timestamp,
                         whisker_timestamp_ms=whisker_timestamp_ms,
                         from_server=from_server)
        self.tasksession.events.append(eventobj)

    def create_new_trial(self):
        self.stage = self.config.stages[self.stagenum]
        if self.trial is not None:
            trialnum = self.trial.trialnum + 1
        else:
            trialnum = 1  # first trial
        self.trial = Trial(trialnum=trialnum,
                           started_at=arrow.now(),
                           stage_id=self.stage.id,
                           stagenum=self.stage.stagenum)
        self.tasksession.trials.append(self.trial)
        self.eventnum_in_trial = 0

    # -------------------------------------------------------------------------
    # Connection and startup
    # -------------------------------------------------------------------------

    @exit_on_exception
    def on_connect(self):
        log.info("SerialOrderTask: on_connect")
        self.whisker.timestamps(True)
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
        for d in DEV_DI.values():
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_INPUT)
        for d in DEV_DO.values():
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_OUTPUT)
        log.info("... devices successfully claimed")

    def start_task(self):
        self.tasksession = Session(config_id=self.config_id,
                                   started_at=arrow.now())
        self.dbsession.add(self.tasksession)
        self.whisker.line_set_event(DEV_DI.MAGSENSOR, WEV.MAGPOKE)
        for h in ALL_HOLE_NUMS:
            self.whisker.line_set_event(DEV_DI.get('HOLE_{}'.format(h)),
                                        WEV.get('RESPONSE_{}'.format(h)))
        self.record_event(TEV.TRIAL_START)
        self.report("Started.")
        self.start_new_trial()
        self.dbsession.commit()
        self.whisker.debug_callbacks()  # ***

    # -------------------------------------------------------------------------
    # Event processing
    # -------------------------------------------------------------------------

    def start_new_trial(self):
        self.create_new_trial()
        self.current_sequence = [3, 2, 1]  # ***
        self.trial.set_sequence(self.current_sequence)
        self.record_event(TEV.START_TRIAL)
        self.whisker.line_on(DEV_DO.HOUSELIGHT)
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        self.state = TaskState.awaiting_initiation

    @exit_on_exception  # @Slot(str, datetime.datetime, int)
    def on_event(self, event, timestamp, whisker_timestamp_ms):
        log.info("SerialOrderTask: on_event: {}".format(event))
        self.record_event(event, timestamp, whisker_timestamp_ms,
                          from_server=True)
        self.event_processor(event, timestamp)
        self.dbsession.commit()

    def event_processor(self, event, timestamp):
        # Timers
        if event == WEV.ITI_END and self.state == TaskState.iti:
            return self.decide_re_next_trial()
        if event == WEV.REINF_END and self.state == TaskState.reinforcing:
            return self.start_iti()

        # Responses
        if event == WEV.MAGPOKE:
            if self.state == TaskState.awaiting_initiation:
                return self.show_next_light()
            elif self.state == TaskState.awaiting_foodmag_after_light:
                return self.show_next_light()
            else:
                return
        holenum = get_response_hole_from_event(event)
        if holenum is not None:
            # response to a hole
            if self.state == TaskState.presenting_choice:
                if holenum == self.current_sequence[0]:
                    # correct hole
                    return self.require_next_mag()
                else:
                    # wrong hole
                    return self.start_iti()
            elif self.state == TaskState.presenting_light:
                return self.choice_made(holenum, timestamp)
            elif self.state in [TaskState.awaiting_initiation,
                                TaskState.awaiting_foodmag_after_light]:
                self.trials.n_premature += 1
            else:
                return

        log.warn("Unknown event received: {}".format(event))

    def show_next_light(self):
        if not self.current_sequence:
            return self.offer_choice()
        holenum = self.current_sequence.pop(0)
        self.record_event(TEV.get('PRESENT_LIGHT_{}'.format(holenum)))
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.whisker.line_on(get_stimlight_line(holenum))
        self.state = TaskState.presenting_light

    def require_next_mag(self):
        self.record_event(TEV.REQUIRE_MAGPOKE)
        self.set_all_hole_lights_off()
        self.line_on(DEV_DO.MAGLIGHT)
        self.state = TaskState.awaiting_foodmag_after_light

    def offer_choice(self):
        self.trial.set_choice([1, 2])  # ***
        self.record_event(TEV.PRESENT_CHOICE)
        for holenum in self.trial.choice_holes:
            self.whisker.line_on(get_stimlight_line(holenum))
        self.state = TaskState.presenting_choice

    def choice_made(self, response_hole, timestamp):
        self.session.trials_responded += 1
        correct = self.trial.record_response(response_hole, timestamp)
        if correct:
            self.tasksession.trials_correct += 1
            self.reinforce()
        else:
            self.start_iti()

    def reinforce(self):
        self.record_event(TEV.REINFORCE)
        duration_ms = self.whisker.flash_line_pulses(
            DEV_DO.PELLET,
            count=self.config.reinf_n_pellets,
            on_ms=self.config.reinf_pellet_pulse_ms,
            off_ms=self.reinf_interpellet_gap_ms,
            on_at_rest=False)
        self.timer(WEV.REINF_END, duration_ms)
        self.state = TaskState.reinforcing

    def start_iti(self):
        self.record_event(TEV.ITI_START)
        self.whisker.line_off(DEV_DO.HOUSELIGHT)
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.set_all_hole_lights_off()
        self.timer(WEV.ITI_FINISHED, self.config.iti_duration_ms)
        self.state = TaskState.iti

    def iti_finished(self):
        self.record_event(WEV.ITI_END)
        self.record_event(WEV.TRIAL_END)
        self.decide_re_next_trial()

    def decide_re_next_trial(self):
        trials_this_stage = self.dbsession.query(Trial).filter(
            Trial.stagenum == self.stagenum)
        if len(trials_this_stage) >= self.stage.progression_criterion_y:
            # Maybe we've passed the stage.
            last_y_trials = trials_this_stage[
                -self.stage.progression_criterion_y:]
            n_correct = sum(
                x.response_correct if x.response_correct is not None else 0
                for x in last_y_trials)
            if n_correct >= self.stage.progression_criterion_x:
                return self.progress_to_next_stage()
        if len(trials_this_stage) >= self.stage.stop_after_n_trials:
            # We've reached the end without passing, so we stop.
            return self.end_session()
        self.start_new_trial()

    def progress_to_next_stage(self):
        self.stagenum += 1
        if self.stagenum >= len(self.config.stages):
            self.end_session()
        else:
            self.start_new_trial()

    def end_session(self):
        self.record_event(TEV.SESSION_END)
        self.whisker.timer_clear_all_events()
        self.whisker.clear_all_callbacks()
        for d in DEV_DO.values():
            self.line_off(d)
        self.state = TaskState.finished

    # -------------------------------------------------------------------------
    # Ancillary functions
    # -------------------------------------------------------------------------

    def set_all_hole_lights_off(self):
        for h in ALL_HOLE_NUMS:
            self.line_off(get_stimlight_line(h))

    def create_sequence(self, seqlen=2):
sequences = list(itertools.permutations(ALL_HOLE_NUMS, seqlen))
serial_order_choices = list(itertools.combinations(
    range(1, seqlen + 1), 2))
triallist = [
    TrialPlan(x[0], x[1])
    for x in itertools.product(sequences, serial_order_choices)]
# The rightmost thing in product() will vary fastest,
# and the leftmost slowest. Not that this matter, because:
block_shuffle_by_attr(
    triallist, ["sequence", "hole_choice", "serial_order_choice"])
# This means that serial_order_choice will vary fastest.
shuffle_where_equal_by_attr(triallist, "serial_order_choice")
log.debug("sequence: {}".format([x.sequence for x in triallist]))
log.debug("hole_choice: {}".format([x.hole_choice for x in triallist]))
log.debug("serial_order_choice: {}".format(
    [x.serial_order_choice for x in triallist]))
