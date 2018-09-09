#!/usr/bin/env python
# whisker_serial_order/task.py

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

Core implementation of the Whisker serial order task.

"""

from enum import Enum, unique
import itertools
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, TextIO

import arrow
from cardinal_pythonlib.file_io import writelines_nl
from cardinal_pythonlib.sqlalchemy.dump import (
    dump_connection_info,
    dump_orm_tree_as_insert_sql,
    dump_ddl,
)
from cardinal_pythonlib.sql.literals import sql_comment
from PyQt5.QtCore import pyqtSignal
from whisker.api import min_to_ms, s_to_ms
from whisker.exceptions import WhiskerCommandFailed
from whisker.qtclient import WhiskerTask
from whisker.qt import exit_on_exception
from whisker.random import block_shuffle_by_attr, shuffle_where_equal_by_attr
from whisker.sqlalchemy import get_database_session_thread_scope
from whisker_serial_order.constants import (
    ALL_HOLE_NUMS,
    DEV_DI,
    DEV_DO,
    N_HOLES_FOR_CHOICE,
    MAX_SEQUENCE_LENGTH,
    MIN_SEQUENCE_LENGTH,
    TEV,
    WEV,
)
from whisker_serial_order.models import (
    Base,
    Config,
    TaskSession,
    TestHoleRestrictions,
    Trial,
    Event,
    TrialPlan,
)
from whisker_serial_order.settings import get_output_directory
from whisker_serial_order.version import SERIAL_ORDER_VERSION

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

@unique
class TaskState(Enum):
    """
    Enum to represent the state of the task.
    """
    not_started = 0
    awaiting_initiation = 1
    presenting_light = 2
    awaiting_foodmag_after_light = 3
    presenting_choice = 4
    reinforcing = 5
    awaiting_food_collection = 6  # keeps maglight on
    iti = 7
    finished = 8


# =============================================================================
# Helper functions
# =============================================================================

def get_hole_line(h: int) -> str:
    """
    Returns the name of the Whisker input line for a specified hole.

    :param h: 1-based hole number.
    """
    return DEV_DI["HOLE_{}".format(h)]


def get_stimlight_line(h: int) -> str:
    """
    Returns the name of the Whisker output line for a specified hole's light.

    :param h: 1-based hole number.
    """
    return DEV_DO["STIMLIGHT_{}".format(h)]


def get_response_hole_from_event(ev: str) -> Optional[int]:
    """
    Returns a hole number from a response event string, or None if it's not a
    matching event.
    """
    for h in ALL_HOLE_NUMS:
        if ev == WEV.get('RESPONSE_{}'.format(h), None):
            return h
    return None


# =============================================================================
# Task
# =============================================================================

class SerialOrderTask(WhiskerTask):
    """
    Core class representing the Whisker implementation of the serial order
    task.
    """
    task_status_sig = pyqtSignal(str)
    task_started_sig = pyqtSignal()
    task_finished_sig = pyqtSignal()

    # -------------------------------------------------------------------------
    # Creation, thread startup, shutdown.
    # -------------------------------------------------------------------------

    def __init__(self, dbsettings: Dict[str, Any], config_id: int) -> None:
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
        self.stagenum = None  # ONE-based
        self.state = TaskState.not_started
        self.trialplans = []
        self.current_sequence = []
        self.timeouts = []
        self.session_time_expired = False
        self.file_written = False

    def thread_started(self) -> None:
        """
        Called when the thread is started.
        Establishes a database session and config.
        """
        log.debug("thread_started")
        self.dbsession = get_database_session_thread_scope(self.dbsettings)
        # ... keep the session running, if we can; simpler
        self.config = self.dbsession.query(Config).get(self.config_id)

    @exit_on_exception
    def stop(self) -> None:
        """
        Saves data to the output file, COMMITs and closes the database, and
        generally cleans up.
        """
        self.save_to_file()
        self.dbsession.commit()
        self.dbsession.close()
        super().stop()
        self.task_finished_sig.emit()

    # -------------------------------------------------------------------------
    # Shortcuts
    # -------------------------------------------------------------------------

    def cmd(self, *args, **kwargs) -> None:
        """
        Executes a Whisker command.
        """
        self.whisker.command_exc(*args, **kwargs)

    def timer(self, *args, **kwargs) -> None:
        """
        Sets a Whisker timer.
        """
        self.whisker.timer_set_event(*args, **kwargs)

    def cancel_timer(self, event: str) -> None:
        """
        Cancels a Whisker timer.
        """
        self.whisker.timer_clear_event(event)

    def add_timeout(self, event: str, duration_ms: int) -> None:
        """
        Adds an internal timeout.
        """
        self.timer(event, duration_ms)
        self.timeouts.append(event)

    def set_limhold(self, event: str) -> None:
        """
        Sets a timeout for the stage's limited hold period.
        """
        self.add_timeout(event, s_to_ms(self.stage.limited_hold_s))

    def cancel_timeouts(self) -> None:
        """
        Cancels all pending timeouts.
        """
        for event in self.timeouts:
            self.cancel_timer(event)
        self.timeouts = []

    def report(self, msg: str) -> None:
        """
        Sends a status message.
        """
        self.task_status_sig.emit(msg)

    def record_event(self, event: str, timestamp: arrow.Arrow = None,
                     whisker_timestamp_ms: int = None,
                     from_server: bool = False) -> None:
        """
        Records an :class:`.Event`.
        """
        if timestamp is None:
            timestamp = arrow.now()
        self.eventnum_in_session += 1
        if self.trial:
            trial_id = self.trial.trial_id
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
        log.info(event)

    def create_new_trial(self) -> None:
        """
        Creates a new :class:`.Trial` object.

        .. todo:: implement hole restrictions, SerialOrderTask.create_new_trial
        """
        assert self.stagenum is not None
        self.stage = self.config.stages[self.stagenum - 1]
        if self.trial is not None:
            trialnum = self.trial.trialnum + 1
        else:
            trialnum = 1  # first trial
        self.trial = Trial(trialnum=trialnum,
                           started_at=arrow.now(),
                           config_stage_id=self.stage.config_stage_id,
                           stagenum=self.stage.stagenum)
        trialplan = self.get_trial_plan(self.stage.sequence_length)
        self.trial.set_sequence(trialplan.sequence)
        self.trial.set_choice(trialplan.hole_choice)
        self.tasksession.trials.append(self.trial)
        self.eventnum_in_trial = 0
        self.current_sequence = list(trialplan.sequence)
        # ... make a copy, but also convert from tuple to list
        self.dbsession.flush()  # sets the trial_id variable

    # -------------------------------------------------------------------------
    # Connection and startup
    # -------------------------------------------------------------------------

    @exit_on_exception
    def on_connect(self) -> None:
        """
        Called when we have connected to the Whisker server.
        Tells the server some status information and starts the task.
        """
        self.info("Connected")
        self.whisker.timestamps(True)
        self.whisker.report_name("SerialOrder", SERIAL_ORDER_VERSION)
        try:
            self.claim()
            self.start_task()
        except WhiskerCommandFailed as e:
            self.critical(
                "Command failed: {}".format(e.args[0] if e.args else '?'))

    def claim(self) -> None:
        """
        Claims Whisker devices.
        """
        self.info("Claiming devices...")
        self.whisker.claim_group(self.config.devicegroup)
        for d in DEV_DI.values():
            self.whisker.claim_line(group=self.config.devicegroup, device=d,
                                    output=False)
        for d in DEV_DO.values():
            self.whisker.claim_line(group=self.config.devicegroup, device=d,
                                    output=True)
        self.info("... devices successfully claimed")

    def start_task(self) -> None:
        """
        Starts the task.
        """
        self.task_started_sig.emit()
        self.tasksession = TaskSession(config_id=self.config_id,
                                       started_at=arrow.now())
        self.dbsession.add(self.tasksession)
        self.whisker.line_set_event(DEV_DI.MAGSENSOR, WEV.MAGPOKE)
        for h in ALL_HOLE_NUMS:
            self.whisker.line_set_event(DEV_DI.get('HOLE_{}'.format(h)),
                                        WEV.get('RESPONSE_{}'.format(h)))
        self.record_event(TEV.SESSION_START)
        self.timer(WEV.SESSION_TIME_OVER,
                   min_to_ms(self.config.session_time_limit_min))
        self.info("Started.")
        self.progress_to_next_stage(first=True)
        self.dbsession.commit()
        # self.whisker.debug_callbacks()

    # -------------------------------------------------------------------------
    # Event processing
    # -------------------------------------------------------------------------

    def start_new_trial(self) -> None:
        """
        Starts a new trial.
        """
        self.create_new_trial()
        self.record_event(TEV.TRIAL_START)
        self.whisker.line_on(DEV_DO.HOUSELIGHT)
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        self.set_all_hole_lights_off()
        self.state = TaskState.awaiting_initiation
        self.report("Awaiting initiation at food magazine")

    @exit_on_exception  # @pyqtSlot(str, arrow.Arrow, int)
    def on_event(self, event: str, timestamp: arrow.Arrow,
                 whisker_timestamp_ms: int) -> None:
        """
        Response to Whisker events.
        (Records and processes the event.)
        """
        # log.info("SerialOrderTask: on_event: {}".format(event))
        self.record_event(event, timestamp, whisker_timestamp_ms,
                          from_server=True)
        self.event_processor(event, timestamp)
        self.dbsession.commit()

    def event_processor(self, event: str, timestamp: arrow.Arrow) -> None:
        """
        Main function to deal with incoming Whisker events.
        Implements the task's logic.
        """
        # ---------------------------------------------------------------------
        # Timers
        # ---------------------------------------------------------------------
        if event == WEV.TIMEOUT_NO_RESPONSE_TO_LIGHT:
            if self.state == TaskState.presenting_light:
                self.start_iti(timestamp)
            return
        if event == WEV.TIMEOUT_NO_RESPONSE_TO_MAG:
            if self.state == TaskState.awaiting_foodmag_after_light:
                self.start_iti(timestamp)
            return
        if event == WEV.TIMEOUT_NO_RESPONSE_TO_CHOICE:
            if self.state == TaskState.presenting_choice:
                self.start_iti(timestamp)
            return
        if event == WEV.REINF_END:
            if self.state == TaskState.reinforcing:
                self.reinforcement_delivery_finished(timestamp)
            return
        if event == WEV.TIMEOUT_FOOD_UNCOLLECTED:
            if self.state == TaskState.awaiting_food_collection:
                self.start_iti(timestamp)
            return
        if event == WEV.ITI_END:
            if self.state == TaskState.iti:
                self.iti_finished_end_trial()
            return
        if event == WEV.SESSION_TIME_OVER:
            self.info("Session time expired.")
            self.session_time_expired = True
            return

        # ---------------------------------------------------------------------
        # Responses
        # ---------------------------------------------------------------------
        if event == WEV.MAGPOKE:
            if self.state == TaskState.awaiting_initiation:
                self.trial.record_initiation(timestamp)
                self.show_next_light(timestamp)
            elif self.state == TaskState.awaiting_foodmag_after_light:
                self.cancel_timeouts()
                self.mag_responded_show_next_light(timestamp)
            elif (self.state == TaskState.reinforcing or
                    self.state == TaskState.awaiting_food_collection or
                    (self.state == TaskState.iti and
                        self.trial.was_reinforced())):
                self.reinforcement_collected(timestamp)
            return

        holenum = get_response_hole_from_event(event)
        if holenum is not None:
            # response to a hole
            if self.state == TaskState.presenting_light:
                self.cancel_timeouts()
                assert self.current_sequence
                if holenum == self.current_sequence[0]:
                    # correct hole
                    return self.seq_responded_require_next_mag(timestamp)
                else:
                    # wrong hole
                    return self.start_iti(timestamp)
            elif self.state == TaskState.presenting_choice:
                self.cancel_timeouts()
                if holenum in self.trial.choice_holes:
                    # Responded to one of the choices
                    return self.choice_made(holenum, timestamp)
                else:
                    # Reponded elsewhere
                    return self.start_iti(timestamp)
            elif self.state in [TaskState.awaiting_initiation,
                                TaskState.awaiting_foodmag_after_light]:
                self.trial.record_premature(timestamp)
            return

        log.warning("Unknown event received: {}".format(event))

    def show_next_light(self, timestamp: arrow.Arrow) -> None:
        """
        Shows the next light in the sequence (or moves on to the choice phase
        if all are complete).
        """
        if not self.current_sequence:
            return self.offer_choice(timestamp)
        holenum = self.current_sequence[0]
        self.trial.record_sequence_hole_lit(timestamp, holenum)
        self.record_event(TEV.get('PRESENT_LIGHT_{}'.format(holenum)))
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.whisker.line_on(get_stimlight_line(holenum))
        self.set_limhold(WEV.TIMEOUT_NO_RESPONSE_TO_LIGHT)
        self.state = TaskState.presenting_light
        self.report("Presenting light {} (from sequence {})".format(
            holenum,
            self.trial.get_sequence_holes_as_str(),
        ))

    def seq_responded_require_next_mag(self, timestamp: arrow.Arrow) -> None:
        """
        Called when the subject has responded to a hole in the sequence;
        records details and offers the food magazine light.
        """
        self.trial.record_sequence_hole_response(timestamp)
        self.record_event(TEV.REQUIRE_MAGPOKE)
        self.trial.record_sequence_mag_lit(timestamp)
        self.set_all_hole_lights_off()
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        self.current_sequence.pop(0)
        self.set_limhold(WEV.TIMEOUT_NO_RESPONSE_TO_MAG)
        self.state = TaskState.awaiting_foodmag_after_light
        self.report("Awaiting magazine response after response to light")

    def mag_responded_show_next_light(self, timestamp: arrow.Arrow) -> None:
        """
        Called when the subject has responded to the food magazine during the
        sequence; moves on to the next light in the sequence (or to the choice
        if all are complete).
        """
        self.trial.record_sequence_mag_response(timestamp)
        self.show_next_light(timestamp)

    def offer_choice(self, timestamp: arrow.Arrow) -> None:
        """
        Offers the choice. "Which came first?"
        """
        self.record_event(TEV.PRESENT_CHOICE)
        self.trial.record_choice_offered(timestamp)
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        for holenum in self.trial.choice_holes:
            self.whisker.line_on(get_stimlight_line(holenum))
        self.set_limhold(WEV.TIMEOUT_NO_RESPONSE_TO_CHOICE)
        self.state = TaskState.presenting_choice
        self.report("Presenting choice {} (after sequence {})".format(
            self.trial.get_choice_holes_as_str(),
            self.trial.get_sequence_holes_as_str(),
        ))

    def choice_made(self, response_hole: int, timestamp: arrow.Arrow) -> None:
        """
        Called when the subject has made a choice.
        Delivers reinforcement if it was correct, or moves to the ITI
        otherwise.
        """
        self.tasksession.trials_responded += 1
        correct = self.trial.record_response(response_hole, timestamp)
        if correct:
            self.tasksession.trials_correct += 1
            self.reinforce(timestamp)
        else:
            self.start_iti(timestamp)

    def reinforce(self, timestamp: arrow.Arrow) -> None:
        """
        Delivers reinforcement.
        """
        self.record_event(TEV.REINFORCE)
        self.trial.record_reinforcement(timestamp)
        self.set_all_hole_lights_off()
        self.whisker.line_on(DEV_DO.MAGLIGHT)
        duration_ms = self.whisker.flash_line_pulses(
            DEV_DO.PELLET,
            count=self.config.reinf_n_pellets,
            on_ms=self.config.reinf_pellet_pulse_ms,
            off_ms=self.config.reinf_interpellet_gap_ms,
            on_at_rest=False)
        self.timer(WEV.REINF_END, duration_ms)
        self.state = TaskState.reinforcing
        self.report("Reinforcing")

    def reinforcement_delivery_finished(self, timestamp: arrow.Arrow) -> None:
        """
        Reinforcement delivery has finished. Wait for it to be collected, or
        move to the ITI if it's been collected already.
        """
        if self.trial.was_reinf_collected():
            self.start_iti(timestamp)
        else:
            self.state = TaskState.awaiting_food_collection
            self.set_limhold(WEV.TIMEOUT_FOOD_UNCOLLECTED)
            self.report("Awaiting food collection")

    def reinforcement_collected(self, timestamp: arrow.Arrow) -> None:
        """
        Reinforcement has been collected. If this is the first collection event
        for this reinforcer, then if reinforcement is still being delivered,
        hang on (but if not, move to the ITI).
        """
        if self.trial.was_reinf_collected():
            return
        self.trial.record_reinf_collection(timestamp)
        if self.state == TaskState.reinforcing:
            self.whisker.line_off(DEV_DO.MAGLIGHT)
        elif self.state == TaskState.awaiting_food_collection:
            self.start_iti(timestamp)
        # ... but if it's iti already, then do nothing

    def start_iti(self, timestamp: arrow.Arrow) -> None:
        """
        Start the intertrial interval (ITI).
        """
        self.record_event(TEV.ITI_START)
        self.trial.record_iti_start(timestamp)
        self.whisker.line_off(DEV_DO.HOUSELIGHT)
        self.whisker.line_off(DEV_DO.MAGLIGHT)
        self.set_all_hole_lights_off()
        self.timer(WEV.ITI_END, self.config.iti_duration_ms)
        self.state = TaskState.iti
        self.report("ITI")
        log.info("Starting ITI")

    def iti_finished_end_trial(self) -> None:
        """
        The ITI has finished; decide whether we'll deliver another trial.
        :return:
        """
        self.record_event(TEV.TRIAL_END)
        if self.trial.responded or not self.config.repeat_incomplete_trials:
            if self.trialplans:
                log.info("Advancing to next trial plan")
                self.trialplans.pop(0)
            else:
                log.warning("Bug? No trial plan to remove.")
        self.decide_re_next_trial()

    def decide_re_next_trial(self) -> None:
        """
        Work out whether we should be delivering more trials, and/or advancing
        to a new stage. Start the new trial, unless we've finished (in which
        case end the session).
        """
        # Manual way:
        trials_this_stage = self.dbsession.query(Trial)\
            .filter(Trial.session_id == self.tasksession.session_id)\
            .filter(Trial.stagenum == self.stagenum)\
            .order_by(Trial.trialnum)\
            .all()

        # Relationship way, IF appropriately configured
        # ... http://stackoverflow.com/questions/11578070/sqlalchemy-instrumentedlist-object-has-no-attribute-filter  # noqa
        # ... http://docs.sqlalchemy.org/en/rel_0_7/orm/collections.html#dynamic-relationship  # noqa
        # trials_this_stage = self.tasksession.trials\
        #     .filter(Trial.stagenum == self.stagenum)\
        #     .count()

        # Have we run out of time? Then we will definitely stop.
        if self.session_time_expired:
            self.info("Session time expired/no trial in progress; finishing.")
            return self.end_session()

        if len(trials_this_stage) >= self.stage.progression_criterion_y:
            # Maybe we've passed the stage.
            last_y_trials = trials_this_stage[
                -self.stage.progression_criterion_y:]
            n_correct = sum(
                x.response_correct if x.response_correct is not None else 0
                for x in last_y_trials)
            if n_correct >= self.stage.progression_criterion_x:
                self.info("Passed the stage.")
                return self.progress_to_next_stage()
        if len(trials_this_stage) >= self.stage.stop_after_n_trials:
            self.info("We've reached the end without passing, so we stop.")
            return self.end_session()
        self.start_new_trial()

    def progress_to_next_stage(self, first: bool = False) -> None:
        """
        Advances to the next stage.
        """
        self.trialplans = []
        if first:
            self.stagenum = 1
        else:
            self.stagenum += 1
        if self.stagenum > len(self.config.stages):
            self.info("No more stages; finishing.")
            self.end_session()
        else:
            self.start_new_trial()

    def end_session(self) -> None:
        """
        Ends a session, saving data to the disk file.
        """
        self.info("Ending session")
        self.record_event(TEV.SESSION_END)
        self.whisker.timer_clear_all_events()
        self.whisker.clear_all_callbacks()
        self.whisker.line_clear_all_events()
        for d in DEV_DO.values():
            self.whisker.line_off(d)
        self.state = TaskState.finished
        self.save_to_file()
        self.report("Finished")
        self.task_finished_sig.emit()

    def abort(self) -> None:
        """
        Called when a session is being aborted. Saves data to the disk file.
        """
        self.info("Aborting session")
        self.save_to_file()

    # -------------------------------------------------------------------------
    # Device control functions
    # -------------------------------------------------------------------------

    def set_all_hole_lights_off(self) -> None:
        """
        Turns all hole lights off.
        """
        for h in ALL_HOLE_NUMS:
            self.whisker.line_off(get_stimlight_line(h))

    # -------------------------------------------------------------------------
    # Trial planning
    # -------------------------------------------------------------------------

    def get_trial_plan(self, seqlen: int) -> TrialPlan:
        """
        Fetches the next trial plan, or repopulates our internal list if it's
        empty (thus implementing the draw-without-replacement system).

        :param seqlen: length of the sequence to implement.
        :return: a :class:`.TrialPlan`.

        .. todo:: implement hole restrictions, SerialOrderTask.get_trial_plan

        """
        # This implements part of a draw-without-replacement system
        if not self.trialplans:  # we need more!
            self.trialplans = self.create_trial_plans(seqlen)
        return self.trialplans[0]  # draw one
        # removal occurs elsewhere - see iti_finished_end_trial()

    @staticmethod
    def create_trial_plans(
            seqlen: int,
            test_hole_restrictions: TestHoleRestrictions = None) \
            -> List[TrialPlan]:
        """
        Generates a new shuffled list of trial plans, for a given sequence
        length (± choice hole restrictions).

        :param seqlen: sequence length
        :param test_hole_restrictions: a :class:`.TestHoleRestrictions`
            object, or ``None``
        :return: a shuffled list of :class:`.TrialPlan` objects.
        """
        log.info("Generating new trial plans")
        assert MIN_SEQUENCE_LENGTH <= seqlen <= MAX_SEQUENCE_LENGTH, (
            "Sequence length ({}) must be in range [{}, {}]".format(
                seqlen, MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_LENGTH)
        )

        sequences = list(itertools.permutations(ALL_HOLE_NUMS, seqlen))
        # ... a list of lists of holes

        serial_order_choices = list(itertools.combinations(
            range(1, seqlen + 1), N_HOLES_FOR_CHOICE))
        # ... a list of lists of temporal (serial order) positions, not holes

        triallist = [
            TrialPlan(x[0], x[1])
            for x in itertools.product(sequences, serial_order_choices)]
        # The rightmost thing in product() will vary fastest,
        # and the leftmost slowest. Not that this matters, because we shuffle
        # below.

        # But first, any restrictions?
        if test_hole_restrictions:
            triallist = [t for t in triallist
                         if t.meets_restrictions(test_hole_restrictions)]

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

    # -------------------------------------------------------------------------
    # Text-based results save, as SQL
    # -------------------------------------------------------------------------

    def save_to_file(self) -> None:
        """
        Writes data (in SQL format) to a suitably named output text file in
        the chosen output directory.
        """
        if self.file_written:
            return
        if not self.tasksession:
            self.info("No session yet; nothing to write to disk.")
            return
        filename = os.path.join(
            get_output_directory(),
            "wso_{dt}_{subj}.sql".format(
                dt=self.tasksession.started_at.format("YYYY-MM-DDTHHmmss"),
                # ... avoid ':' for Windows filenames
                subj=self.config.subject
            )
        )
        self.tasksession.filename = filename
        self.dbsession.commit()
        self.info("Writing data to: {}".format(filename))
        try:
            with open(filename, 'w') as fileobj:
                # noinspection PyTypeChecker
                self.save_to_sql(fileobj, filename)
            self.file_written = True
        except Exception as e:
            self.critical("Failed to write to {}; exception: {}".format(
                filename, e))

    def save_to_sql(self, fileobj: TextIO, filename: str) -> None:
        """
        Writes a SQLAlchemy ORM tree, as SQL, to a disk file.

        :param fileobj: the file-like object to which to write
        :param filename: the filename (for cosmetic purposes only)
        """
        session = self.dbsession
        engine = session.bind
        writelines_nl(fileobj, [
            sql_comment('whisker_serial_order data file'),
            sql_comment('Filename: {}'.format(filename)),
            sql_comment('Created at: {}'.format(arrow.now())),
            sql_comment('=' * 76)
        ])
        dump_connection_info(engine, fileobj)
        dump_ddl(Base.metadata, dialect_name=engine.dialect.name,
                 fileobj=fileobj)
        dump_orm_tree_as_insert_sql(engine, self.tasksession, fileobj)
