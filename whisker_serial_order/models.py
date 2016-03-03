#!/usr/bin/env python
# whisker_serial_order/models.py

import datetime
import logging
log = logging.getLogger(__name__)

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship

from sqlalchemy_utils import JSONType
from whisker.lang import (
    OrderedNamespace,
    ordered_repr,
    simple_repr,
    trunc_if_integer,
)
from whisker.sqlalchemysupport import (
    ALEMBIC_NAMING_CONVENTION,
    deepcopy_sqla_object,
    SqlAlchemyAttrDictMixin,
)

from .constants import DATETIME_FORMAT_PRETTY

# =============================================================================
# SQLAlchemy base.
# =============================================================================
# Derived classes will share the specified metadata.

MASTER_META = MetaData(naming_convention=ALEMBIC_NAMING_CONVENTION)
Base = declarative_base(metadata=MASTER_META)


# =============================================================================
# Program configuration
# =============================================================================

class Config(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)
    read_only = Column(Boolean)  # used for a live task, therefore can't edit
    # Whisker
    server = Column(String)
    port = Column(Integer)
    devicegroup = Column(String)
    # Subject
    subject = Column(String)
    # Reinforcement
    reinf_n_pellets = Column(Integer)
    reinf_pellet_pulse_ms = Column(Integer)
    reinf_interpellet_gap_ms = Column(Integer)

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


# =============================================================================
# Session summary details
# =============================================================================

class Session(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'session'
    id = Column(Integer, primary_key=True)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)
    config_id = Column(Integer, ForeignKey('config.id'))
    trials = relationship("Trial")


# =============================================================================
# Trial details
# =============================================================================

class Trial(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'trial'
    id = Column(Integer, primary_key=True)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)
    session_id = Column(Integer, ForeignKey('session.id'))
    events = relationship("Event")


# =============================================================================
# Event details
# =============================================================================

class Event(SqlAlchemyAttrDictMixin, Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)
    trial_id = Column(Integer, ForeignKey('trial.id'))
