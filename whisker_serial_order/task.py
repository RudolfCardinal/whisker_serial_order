#!/usr/bin/env python
# whisker_serial_order/task.py

from enum import Enum, unique
import itertools
import logging
log = logging.getLogger(__name__)

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
from whisker.qt import exit_on_exception
from whisker.random import block_shuffle_by_attr, shuffle_where_equal_by_attr
from whisker.sqlalchemy import get_database_session_thread_scope

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
        self.stagenum = None
        self.state = TaskState.not_started
        self.trialplans = []
        self.current_sequence = []

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
        assert self.stagenum is not None
        self.stage = self.config.stages[self.stagenum - 1]
        if self.trial is not None:
            trialnum = self.trial.trialnum + 1
        else:
            trialnum = 1  # first trial
        self.trial = Trial(trialnum=trialnum,
                           started_at=arrow.now(),
                           stage_id=self.stage.id,
                           stagenum=self.stage.stagenum)
        trialplan = self.get_trial_plan(self.stage.sequence_length)
        self.trial.set_sequence(trialplan.sequence)
        self.trial.set_choice(trialplan.hole_choice)
        self.tasksession.trials.append(self.trial)
        self.eventnum_in_trial = 0
        self.current_sequence = list(trialplan.sequence)
        # ... make a copy, but also convert from tuple to list

    # -------------------------------------------------------------------------
    # Connection and startup
    # -------------------------------------------------------------------------

    @exit_on_exception
    def on_connect(self):
        self.info("Connected")
        self.whisker.timestamps(True)
        self.whisker.command(CMD_REPORT_NAME, "SerialOrder", VERSION)
        try:
            self.claim()
        except WhiskerCommandFailed as e:
            log.critical(
                "Command failed: {}".format(e.args[0] if e.args else '?'))
        self.start_task()

    def claim(self):
        self.info("Claiming devices...")
        self.cmd(CMD_CLAIM_GROUP, self.config.devicegroup)
        for d in DEV_DI.values():
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_INPUT)
        for d in DEV_DO.values():
            self.cmd(CMD_LINE_CLAIM, self.config.devicegroup, d, FLAG_OUTPUT)
        self.info("... devices successfully claimed")

    def start_task(self):
        self.tasksession = Session(config_id=self.config_id,
                                   started_at=arrow.now())
        self.dbsession.add(self.tasksession)
        self.whisker.line_set_event(DEV_DI.MAGSENSOR, WEV.MAGPOKE)
        for h in ALL_HOLE_NUMS:
            self.whisker.line_set_event(DEV_DI.get('HOLE_{}'.format(h)),
                                        WEV.get('RESPONSE_{}'.format(h)))
        self.record_event(TEV.SESSION_START)
        self.info("Started.")
        self.progress_to_next_stage(first=True)
        self.dbsession.commit()
        # self.whisker.debug_callbacks()

    # -------------------------------------------------------------------------
    # Event processing
    # -------------------------------------------------------------------------

    def start_new_trial(self):
        self.create_new_trial()
        self.record_event(TEV.TRIAL_START)
        self.whisker.line_on(DEV_DO.HOUSELIGHT)
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        self.set_all_hole_lights_off()
        self.state = TaskState.awaiting_initiation
        self.report("Awaiting initiation at food magazine")

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

        # *** turn on maglight at reinforcement, and off on collection

        holenum = get_response_hole_from_event(event)
        if holenum is not None:
            # response to a hole
            if self.state == TaskState.presenting_light:
                assert self.current_sequence
                if holenum == self.current_sequence[0]:
                    # correct hole
                    return self.require_next_mag()
                else:
                    # wrong hole
                    return self.start_iti()
            elif self.state == TaskState.presenting_choice:
                if holenum in self.trial.choice_holes:
                    # Responded to one of the choices
                    return self.choice_made(holenum, timestamp)
                else:
                    # Reponded elsewhere
                    return self.start_iti()
            elif self.state in [TaskState.awaiting_initiation,
                                TaskState.awaiting_foodmag_after_light]:
                self.trials.n_premature += 1
            else:
                return

        log.warn("Unknown event received: {}".format(event))

    def show_next_light(self):
        if not self.current_sequence:
            return self.offer_choice()
        self.trial.sequence_n_offered += 1
        holenum = self.current_sequence[0]
        self.record_event(TEV.get('PRESENT_LIGHT_{}'.format(holenum)))
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.whisker.line_on(get_stimlight_line(holenum))
        self.state = TaskState.presenting_light
        self.report("Presenting light {} (from sequence {})".format(
            holenum,
            self.trial.get_sequence_holes_as_str(),
        ))

    def require_next_mag(self):
        self.record_event(TEV.REQUIRE_MAGPOKE)
        self.set_all_hole_lights_off()
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        self.current_sequence.pop(0)
        self.state = TaskState.awaiting_foodmag_after_light
        self.report("Awaiting magazine response after response to light")

    def offer_choice(self):
        self.record_event(TEV.PRESENT_CHOICE)
        self.trial.choice_offered = True
        for holenum in self.trial.choice_holes:
            self.whisker.line_on(get_stimlight_line(holenum))
        self.state = TaskState.presenting_choice
        self.report("Presenting choice {} (after sequence {})".format(
            self.trial.get_choice_holes_as_str(),
            self.trial.get_sequence_holes_as_str(),
        ))

    def choice_made(self, response_hole, timestamp):
        self.tasksession.trials_responded += 1
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
            off_ms=self.config.reinf_interpellet_gap_ms,
            on_at_rest=False)
        self.timer(WEV.REINF_END, duration_ms)
        self.state = TaskState.reinforcing
        self.report("Reinforcing")

    def start_iti(self):
        self.record_event(TEV.ITI_START)
        self.whisker.line_off(DEV_DO.HOUSELIGHT)
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.set_all_hole_lights_off()
        self.timer(WEV.ITI_END, self.config.iti_duration_ms)
        self.state = TaskState.iti
        self.report("ITI")

    def iti_finished_end_trial(self):
        self.record_event(TEV.TRIAL_END)
        if self.trial.responded or not self.config.repeat_incomplete_trials:
            if self.trialplans:
                self.trialplans.pop(0)
            else:
                log.warning("Bug? No trial plan to remove.")
        self.decide_re_next_trial()

    def decide_re_next_trial(self):
        # Manual way:
        trials_this_stage = self.dbsession.query(Trial)\
            .filter(Trial.session_id == self.tasksession.id)\
            .filter(Trial.stagenum == self.stagenum)\
            .order_by(Trial.trialnum)\
            .all()

        # Relationship way, IF appropriately configured
        # ... http://stackoverflow.com/questions/11578070/sqlalchemy-instrumentedlist-object-has-no-attribute-filter  # noqa
        # ... http://docs.sqlalchemy.org/en/rel_0_7/orm/collections.html#dynamic-relationship  # noqa
        # trials_this_stage = self.tasksession.trials\
        #     .filter(Trial.stagenum == self.stagenum)\
        #     .count()

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

    def progress_to_next_stage(self, first=False):
        self.trialplans = []
        if first:
            self.stagenum = 1
        else:
            self.stagenum += 1
        if self.stagenum >= len(self.config.stages):
            self.end_session()
        else:
            self.start_new_trial()

    def end_session(self):
        self.record_event(TEV.SESSION_END)
        self.whisker.timer_clear_all_events()
        self.whisker.clear_all_callbacks()
        self.whisker.line_clear_all_events()
        for d in DEV_DO.values():
            self.whisker.line_off(d)
        self.state = TaskState.finished
        self.report("Finished")

    # -------------------------------------------------------------------------
    # Device control functions
    # -------------------------------------------------------------------------

    def set_all_hole_lights_off(self):
        for h in ALL_HOLE_NUMS:
            self.whisker.line_off(get_stimlight_line(h))

    # -------------------------------------------------------------------------
    # Trial planning
    # -------------------------------------------------------------------------

    def get_trial_plan(self, seqlen):
        if not self.trialplans:
            self.trialplans = self.create_trial_plans(seqlen)
        return self.trialplans[0]
        # removal occurs elsewhere

    def create_trial_plans(self, seqlen):
        log.info("Generating new trial plans")
        sequences = list(itertools.permutations(ALL_HOLE_NUMS, seqlen))
        serial_order_choices = list(itertools.combinations(
            range(1, seqlen + 1), 2))
        triallist = [
            TrialPlan(x[0], x[1])
            for x in itertools.product(sequences, serial_order_choices)]
        # The rightmost thing in product() will vary fastest,
        # and the leftmost slowest. Not that this matters, because we shuffle:
        block_shuffle_by_attr(
            triallist, ["sequence", "hole_choice", "serial_order_choice"])
        # This means that serial_order_choice will vary fastest.
        shuffle_where_equal_by_attr(triallist, "serial_order_choice")
        log.debug("plans: sequence: {}".format(
            [x.sequence for x in triallist]))
        log.debug("plans: hole_choice: {}".format(
            [x.hole_choice for x in triallist]))
        log.debug("plans: serial_order_choice: {}".format(
            [x.serial_order_choice for x in triallist]))
        return triallist
