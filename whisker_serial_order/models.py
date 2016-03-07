#!/usr/bin/env python
# whisker_serial_order/models.py

import logging
log = logging.getLogger(__name__)

import arrow
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,  # variable length in PostgreSQL; specify length for MySQL
    Text,  # variable length
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from sqlalchemy_utils import (
    JSONType,
    ScalarListType,
)
from whisker.sqlalchemysupport import (
    ALEMBIC_NAMING_CONVENTION,
    ArrowMicrosecondType,
    deepcopy_sqla_object,
    SqlAlchemyAttrDictMixin,
)

from .constants import (
    DATETIME_FORMAT_PRETTY,
    MAX_EVENT_LENGTH,
    N_HOLES,
)

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

    id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    read_only = Column(Boolean)  # used for a live task, therefore can't edit
    stages = relationship("ConfigStage", order_by="ConfigStage.stagenum")

    # Whisker
    server = Column(Text)
    port = Column(Integer)
    devicegroup = Column(Text)
    # Subject
    subject = Column(Text)
    # Reinforcement
    reinf_n_pellets = Column(Integer)
    reinf_pellet_pulse_ms = Column(Integer)
    reinf_interpellet_gap_ms = Column(Integer)
    # ITI
    iti_duration_ms = Column(Integer)

    def __init__(self, **kwargs):
        self.read_only = kwargs.pop('read_only', False)
        self.server = kwargs.pop('server', 'localhost')
        self.port = kwargs.pop('port', 3233)
        self.devicegroup = kwargs.pop('devicegroup', 'box0')
        self.subject = kwargs.pop('subject', '')
        self.reinf_n_pellets = kwargs.pop('reinf_n_pellets', 1)
        self.reinf_pellet_pulse_ms = kwargs.pop('reinf_pellet_pulse_ms', 45)
        self.reinf_interpellet_gap_ms = kwargs.pop('reinf_interpellet_gap_ms',
                                                   250)
        self.iti_duration_ms = kwargs.pop('iti_duration_ms', 2000)

    def __str__(self):
        return (
            "Config {id}: subject = {subject}, server = {server}, "
            "devicegroup = {devicegroup}".format(
                id=self.id,
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
        # *** check stages are copied into frozen copy


class ConfigStage(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'config_stage'

    id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    config_id = Column(Integer, ForeignKey('config.id'), nullable=False)
    stagenum = Column(Integer, nullable=False)  # *** must be consecutive and zero-based

    # Sequence
    sequence_length = Column(Integer)  # ***
    # Progress to next stage when X of last Y correct, or total trials complete
    progression_criterion_x = Column(Integer)  # ***
    progression_criterion_y = Column(Integer)  # ***
    stop_after_n_trials = Column(Integer)  # ***
    # ***

    def __init__(self, **kwargs):
        self.config_id = kwargs.pop('config_id')
        self.stagenum = kwargs.pop('stagenum')


# =============================================================================
# Session summary details
# =============================================================================

class Session(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'session'
    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey('config.id'), nullable=False)
    events = relationship("Event")
    trials = relationship("Trial")

    started_at = Column(ArrowMicrosecondType, nullable=False)

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
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('session.id'), nullable=False)
    events = relationship("Event")
    trialnum = Column(Integer, nullable=False)
    stage_id = Column(Integer, ForeignKey('config_stage.id'), nullable=False)
    stagenum = Column(Integer, nullable=False)

    started_at = Column(ArrowMicrosecondType)

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

    responded = Column(Boolean, nullable=False, default=False)
    responded_at = Column(ArrowMicrosecondType)
    responded_hole = Column(Integer)  # which hole was chosen?
    response_correct = Column(Boolean)

    n_premature = Column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs):
        self.session_id = kwargs.pop('session_id', None)  # may be set later
        self.trialnum = kwargs.pop('trialnum')
        self.started_at = kwargs.pop('started_at')
        self.stage_id = kwargs.pop('stage_id')
        self.stagenum = kwargs.pop('stagenum')
        self.n_premature = 0

    def set_sequence(self, sequence_holes):
        self.sequence_holes = list(sequence_holes)  # make a copy
        self.sequence_length = len(sequence_holes)

    def set_choice(self, choice_holes):
        assert len(choice_holes == 2)
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

    def record_response(self, response_hole, timestamp):
        self.responded = True
        self.responded_at = timestamp
        self.responded_hole = response_hole
        # IMPLEMENTS THE KEY TASK RULE: "Which came first?"
        self.response_correct = response_hole == self.choice_hole_earliest
        return self.response_correct


# =============================================================================
# Event details
# =============================================================================

class Event(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('session.id'), nullable=False)
    eventnum_in_session = Column(Integer, nullable=False, index=True)
    trial_id = Column(Integer, ForeignKey('trial.id'))  # may be NULL
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
