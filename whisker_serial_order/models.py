#!/usr/bin/env python
# whisker_serial_order/models.py

import logging

import arrow
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,  # variable length in PostgreSQL; specify length for MySQL
    Text,  # variable length
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_utils import (
    # JSONType,
    ScalarListType,
)
from whisker.sqlalchemy import (
    ALEMBIC_NAMING_CONVENTION,
    ArrowMicrosecondType,
    deepcopy_sqla_object,
    SqlAlchemyAttrDictMixin,
)

from .constants import (
    DATETIME_FORMAT_PRETTY,
    MAX_EVENT_LENGTH,
)
from .extra import latency_s

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_GENERIC_STRING_LENGTH = 255

# =============================================================================
# SQLAlchemy base.
# =============================================================================
# Derived classes will share the specified metadata.

MASTER_META = MetaData(naming_convention=ALEMBIC_NAMING_CONVENTION)
Base = declarative_base(metadata=MASTER_META)


# =============================================================================
# Helper functions/classes
# =============================================================================

def spatial_to_serial_order(hole_sequence, holes):
    return [hole_sequence.index(h) + 1 for h in holes]


def serial_order_to_spatial(hole_sequence, seq_positions):
    return [hole_sequence[i - 1] for i in seq_positions]


class TrialPlan(object):
    def __init__(self, sequence, serial_order_choice):
        self.sequence = sequence
        self.serial_order_choice = sorted(serial_order_choice)
        self.hole_choice = sorted(
            serial_order_to_spatial(self.sequence, self.serial_order_choice))

    def __repr__(self):
        return (
            "TrialPlan(sequence={}, serial_order_choice={}, "
            "hole_choice={})".format(
                self.sequence, self.serial_order_choice, self.hole_choice)
        )

    @property
    def hole_serial_order_combo(self):
        return self.serial_order_choice + self.hole_choice


# =============================================================================
# Program configuration
# =============================================================================

class Config(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'config'

    config_id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    read_only = Column(Boolean)  # used for a live task, therefore can't edit
    stages = relationship("ConfigStage", order_by="ConfigStage.stagenum")
    # No explicit relationship to Session.
    # This means that deepcopy() won't copy any non-config stuff, which is
    # helpful, but means that we have to use the session as the starting point
    # for the write-to-disk walk.
    # If we wanted to improve this, the other way would be to extend the
    # deepcopy() function to limit the classes it will traverse.

    # Whisker
    server = Column(String(MAX_GENERIC_STRING_LENGTH))
    port = Column(Integer)
    devicegroup = Column(String(MAX_GENERIC_STRING_LENGTH))
    # Subject
    subject = Column(String(MAX_GENERIC_STRING_LENGTH))
    # Reinforcement
    reinf_n_pellets = Column(Integer)
    reinf_pellet_pulse_ms = Column(Integer)
    reinf_interpellet_gap_ms = Column(Integer)
    # ITI
    iti_duration_ms = Column(Integer)
    # Failed trials
    repeat_incomplete_trials = Column(Boolean)
    # Overall limits
    session_time_limit_min = Column(Float)

    def __init__(self, **kwargs):
        """Must be clonable by deepcopy_sqla_object(), so must accept empty
        kwargs."""
        self.read_only = kwargs.pop('read_only', False)
        self.server = kwargs.pop('server', 'localhost')
        self.port = kwargs.pop('port', 3233)
        self.devicegroup = kwargs.pop('devicegroup', 'box0')
        self.subject = kwargs.pop('subject', '')
        self.reinf_n_pellets = kwargs.pop('reinf_n_pellets', 2)
        self.reinf_pellet_pulse_ms = kwargs.pop('reinf_pellet_pulse_ms', 45)
        self.reinf_interpellet_gap_ms = kwargs.pop('reinf_interpellet_gap_ms',
                                                   250)
        self.iti_duration_ms = kwargs.pop('iti_duration_ms', 2000)
        self.session_time_limit_min = kwargs.pop('session_time_limit_min', 60)

    def __str__(self):
        return (
            "Config {config_id}: subject = {subject}, server = {server}, "
            "devicegroup = {devicegroup}".format(
                config_id=self.config_id,
                subject=self.subject,
                server=self.server,
                devicegroup=self.devicegroup,
            )
        )

    def get_modified_at_pretty(self):
        if self.modified_at is None:
            return None
        return self.modified_at.strftime(DATETIME_FORMAT_PRETTY)

    def clone(self, session, read_only=False):
        newconfig = deepcopy_sqla_object(self, session)  # will add to session
        newconfig.read_only = read_only
        session.flush()  # but not necessarily commit
        return newconfig

    def get_n_stages(self):
        return len(self.stages)

    def has_stages(self):
        return self.get_n_stages() > 0


class ConfigStage(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'config_stage'

    config_stage_id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    config_id = Column(Integer, ForeignKey('config.config_id'), nullable=False)
    stagenum = Column(Integer, nullable=False)  # consecutive, 1-based

    # Sequence
    sequence_length = Column(Integer)
    # Limited hold
    limited_hold_s = Column(Float)
    # Progress to next stage when X of last Y correct, or total trials complete
    progression_criterion_x = Column(Integer)
    progression_criterion_y = Column(Integer)
    stop_after_n_trials = Column(Integer)

    def __init__(self, **kwargs):
        """Must be clonable by deepcopy_sqla_object(), so must accept empty
        kwargs."""
        self.config_id = kwargs.pop('config_id', None)
        self.stagenum = kwargs.pop('stagenum', None)
        self.sequence_length = kwargs.pop('sequence_length', None)
        self.limited_hold_s = kwargs.pop('limited_hold_s', 10)
        self.progression_criterion_x = kwargs.pop('progression_criterion_x',
                                                  10)
        self.progression_criterion_y = kwargs.pop('progression_criterion_y',
                                                  12)
        # In R: use binom.test(x, y) to get the p value for these.
        # Here, the defaults are such that progression requires p = 0.03857.
        self.stop_after_n_trials = kwargs.pop('stop_after_n_trials', 100)


# =============================================================================
# Session summary details
# =============================================================================

class Session(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'session'
    session_id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey('config.config_id'), nullable=False)
    config = relationship("Config")
    events = relationship("Event")
    trials = relationship("Trial")

    started_at = Column(ArrowMicrosecondType, nullable=False)
    filename = Column(Text)

    trials_responded = Column(Integer, nullable=False, default=0)
    trials_correct = Column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs):
        self.config_id = kwargs.pop('config_id')
        self.started_at = kwargs.pop('started_at')
        self.trials_responded = 0
        self.trials_correct = 0


# =============================================================================
# Trial details
# =============================================================================

class Trial(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'trial'
    trial_id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('session.session_id'),
                        nullable=False)
    events = relationship("Event")
    sequence_timings = relationship("SequenceTiming")
    trialnum = Column(Integer, nullable=False)
    config_stage_id = Column(Integer,
                             ForeignKey('config_stage.config_stage_id'),
                             nullable=False)
    stagenum = Column(Integer, nullable=False)

    started_at = Column(ArrowMicrosecondType)
    initiated_at = Column(ArrowMicrosecondType)
    initiation_latency_s = Column(Float)

    sequence_holes = Column(ScalarListType(int))  # in order of presentation
    sequence_length = Column(Integer)  # for convenience

    # Various ways of reporting the holes offered, for convenience:
    choice_holes = Column(ScalarListType(int))  # in order of sequence
    choice_seq_positions = Column(ScalarListType(int))  # in order of sequence
    choice_hole_left = Column(Integer)  # hole number, leftmost offered
    choice_hole_right = Column(Integer)  # hole number, rightmost offered
    choice_hole_earliest = Column(Integer)  # hole number, earlist in sequence
    choice_hole_latest = Column(Integer)  # hole number, latest in sequence
    choice_seqpos_earliest = Column(Integer)  # earliest sequence pos offered (1-based)  # noqa
    choice_seqpos_latest = Column(Integer)  # latest sequence pos offered (1-based)  # noqa

    sequence_n_offered = Column(Integer, nullable=False, default=0)
    choice_offered = Column(Boolean, nullable=False, default=False)
    choice_offered_at = Column(ArrowMicrosecondType)

    responded = Column(Boolean, nullable=False, default=False)
    responded_at = Column(ArrowMicrosecondType)
    responded_hole = Column(Integer)  # which hole was chosen?
    response_correct = Column(Boolean)
    response_latency_s = Column(Float)

    reinforced_at = Column(ArrowMicrosecondType)
    reinf_collected_at = Column(ArrowMicrosecondType)
    reinf_collect_latency_s = Column(Float)

    n_premature = Column(Integer, nullable=False, default=0)

    iti_started_at = Column(ArrowMicrosecondType)

    def __init__(self, **kwargs):
        self.session_id = kwargs.pop('session_id', None)  # may be set later
        self.trialnum = kwargs.pop('trialnum')
        self.started_at = kwargs.pop('started_at')
        self.config_stage_id = kwargs.pop('config_stage_id')
        self.stagenum = kwargs.pop('stagenum')
        self.n_premature = 0
        self.sequence_n_offered = 0

        self.sequence_info = None  # current sequence info

    def set_sequence(self, sequence_holes):
        self.sequence_holes = list(sequence_holes)  # make a copy
        self.sequence_length = len(sequence_holes)

    def set_choice(self, choice_holes):
        assert len(choice_holes) == 2
        assert all(x in self.sequence_holes for x in choice_holes)
        # Order choice_holes by sequence_holes:
        self.choice_holes = sorted(choice_holes,
                                   key=lambda x: self.sequence_holes.index(x))
        self.choice_seq_positions = spatial_to_serial_order(
            self.sequence_holes, self.choice_holes)
        self.choice_hole_left = min(self.choice_holes)
        self.choice_hole_right = max(self.choice_holes)
        self.choice_hole_earliest = self.choice_holes[0]
        self.choice_hole_latest = self.choice_holes[-1]
        self.choice_seqpos_earliest = self.sequence_holes.index(
            self.choice_hole_earliest) + 1  # 1-based
        self.choice_seqpos_latest = self.sequence_holes.index(
            self.choice_hole_latest) + 1  # 1-based

    def get_sequence_holes_as_str(self):
        return ",".join(str(x) for x in self.sequence_holes)

    def get_choice_holes_as_str(self):
        return ",".join(str(x) for x in self.choice_holes)

    def record_initiation(self, timestamp):
        self.initiated_at = timestamp
        self.initiation_latency_s = latency_s(self.started_at,
                                              self.initiated_at)

    def record_sequence_hole_lit(self, timestamp, holenum):
        self.sequence_n_offered += 1
        self.sequence_info = SequenceTiming(
            trial_id=self.trial_id,
            seq_pos=self.sequence_n_offered,
            hole_num=holenum,
        )
        self.sequence_info.record_hole_lit(timestamp)
        self.sequence_timings.append(self.sequence_info)

    def record_sequence_hole_response(self, timestamp):
        if self.sequence_info is None:
            return
        self.sequence_info.record_hole_response(timestamp)

    def record_sequence_mag_lit(self, timestamp):
        if self.sequence_info is None:
            return
        self.sequence_info.record_mag_lit(timestamp)

    def record_sequence_mag_response(self, timestamp):
        if self.sequence_info is None:
            return
        self.sequence_info.record_mag_response(timestamp)

    def record_choice_offered(self, timestamp):
        self.choice_offered = True
        self.choice_offered_at = timestamp

    def record_response(self, response_hole, timestamp):
        self.responded = True
        self.responded_at = timestamp
        self.responded_hole = response_hole
        self.response_latency_s = latency_s(self.choice_offered_at,
                                            self.responded_at)
        # IMPLEMENTS THE KEY TASK RULE: "Which came first?"
        self.response_correct = response_hole == self.choice_hole_earliest
        return self.response_correct

    def record_premature(self, timestamp):
        self.n_premature += 1

    def record_reinforcement(self, timestamp):
        self.reinforced_at = timestamp

    def record_reinf_collection(self, timestamp):
        if self.was_reinf_collected():
            return
        self.reinf_collected_at = timestamp
        self.reinf_collect_latency_s = latency_s(self.responded_at,
                                                 self.reinf_collected_at)

    def was_reinforced(self):
        return self.reinforced_at is not None

    def was_reinf_collected(self):
        return self.reinf_collected_at is not None

    def record_iti_start(self, timestamp):
        self.iti_started_at = timestamp
        # And this one's done...
        self.sequence_info = None


# =============================================================================
# Event details
# =============================================================================

class Event(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'event'
    event_id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('session.session_id'),
                        nullable=False)
    eventnum_in_session = Column(Integer, nullable=False, index=True)
    trial_id = Column(Integer, ForeignKey('trial.trial_id'))  # may be NULL
    trialnum = Column(Integer)  # violates DRY for convenience
    eventnum_in_trial = Column(Integer)

    event = Column(String(MAX_EVENT_LENGTH), nullable=False)
    timestamp = Column(ArrowMicrosecondType, nullable=False)
    whisker_timestamp_ms = Column(BigInteger)
    from_server = Column(Boolean)

    def __init__(self, **kwargs):
        self.session_id = kwargs.pop('session_id', None)  # may be set later
        self.eventnum_in_session = kwargs.pop('eventnum_in_session')
        self.trial_id = kwargs.pop('trial_id', None)
        self.trialnum = kwargs.pop('trialnum', None)
        self.eventnum_in_trial = kwargs.pop('eventnum_in_trial', None)
        self.event = kwargs.pop('event')
        self.timestamp = kwargs.pop('timestamp')
        self.whisker_timestamp_ms = kwargs.pop('whisker_timestamp_ms', None)
        self.from_server = kwargs.pop('from_server', False)


# =============================================================================
# Info/timings of the sequences, including response latencies
# =============================================================================

class SequenceTiming(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'sequence_timing'
    sequence_timing_id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey('trial.trial_id'), nullable=False)
    seq_pos = Column(Integer, nullable=False)
    hole_num = Column(Integer, nullable=False)
    hole_lit_at = Column(ArrowMicrosecondType)
    hole_response_at = Column(ArrowMicrosecondType)
    hole_response_latency_s = Column(Float)
    mag_lit_at = Column(ArrowMicrosecondType)
    mag_response_at = Column(ArrowMicrosecondType)
    mag_response_latency_s = Column(Float)

    def __init__(self, **kwargs):
        self.trial_id = kwargs.pop('trial_id')
        self.seq_pos = kwargs.pop('seq_pos')
        self.hole_num = kwargs.pop('hole_num')

    def record_hole_lit(self, timestamp):
        self.hole_lit_at = timestamp

    def record_hole_response(self, timestamp):
        self.hole_response_at = timestamp
        self.hole_response_latency_s = latency_s(self.hole_lit_at,
                                                 self.hole_response_at)

    def record_mag_lit(self, timestamp):
        self.mag_lit_at = timestamp

    def record_mag_response(self, timestamp):
        self.mag_response_at = timestamp
        self.mag_response_latency_s = latency_s(self.mag_lit_at,
                                                self.mag_response_at)
