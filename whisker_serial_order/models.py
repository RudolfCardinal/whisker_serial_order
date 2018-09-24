#!/usr/bin/env python
# whisker_serial_order/models.py

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

SQLAlchemy models and other data storage classes for the serial order task.

"""

from argparse import ArgumentTypeError
import logging
from typing import Any, List, Iterable, Optional, Set, Tuple

import arrow
from cardinal_pythonlib.sqlalchemy.alembic_func import (
    ALEMBIC_NAMING_CONVENTION,
)
from cardinal_pythonlib.sqlalchemy.arrow_types import ArrowMicrosecondType
from cardinal_pythonlib.sqlalchemy.orm_inspect import (
    deepcopy_sqla_object,
    SqlAlchemyAttrDictMixin,
)
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
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql.type_api import TypeDecorator
from sqlalchemy_utils import ScalarListType

from whisker_serial_order.constants import (
    DATETIME_FORMAT_PRETTY,
    MAX_EVENT_LENGTH,
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
    MIN_SERIAL_ORDER_POSITION,
    MAX_SERIAL_ORDER_POSITION,
)
from whisker_serial_order.extra import latency_s
from whisker_serial_order.version import (
    MAX_VERSION_LENGTH,
    SERIAL_ORDER_VERSION,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_GENERIC_STRING_LENGTH = 255
MAX_HOLE_OR_SERIALPOS_PAIR_DEFINITION_STRING_LENGTH = 255  # more than enough!
N_HOLES_FOR_CHOICE = 2


# =============================================================================
# SQLAlchemy base.
# =============================================================================
# Derived classes will share the specified metadata.

MASTER_META = MetaData(naming_convention=ALEMBIC_NAMING_CONVENTION)
Base = declarative_base(metadata=MASTER_META)


# =============================================================================
# Helper functions/classes
# =============================================================================

def spatial_to_serial_order(hole_sequence: List[int],
                            holes: List[int]) -> List[int]:
    """
    Converts a temporal sequence of spatial holes into a list of serial
    order positions.

    Converts the list of spatial holes in use (``hole_sequence``) and the
    temporal sequence of hole indexes (``holes``) into a sequence of spatial
    hole numbers.

    Args:
        hole_sequence: ordered list of spatial hole numbers to be presented
            in the first phase of the task, e.g. [3, 1, 4].

        holes: spatial hole numbers to be enquired about: "what was the
            temporal order of these holes in the first phase?"; e.g. [4, 3].

    Returns:
         list of serial order positions (in this example: [3, 1]).
    """
    return [hole_sequence.index(h) + 1 for h in holes]


def serial_order_to_spatial(hole_sequence: List[int],
                            seq_positions: List[int]) -> List[int]:
    """
    Converts a first-phase hole sequence and a list of serial order positions
    (at the choice phase) into a list of spatial holes at test.

    Args:
        hole_sequence: ordered list of spatial hole numbers to be presented
            in the first phase of the task, e.g. [3, 1, 4].

        seq_positions: list of serial orders, e.g [1, 3] for the first and
            third in the sequence.

    Returns:
         list of spatial hole numbers (e.g. [3, 4] in this example).
    """
    return [hole_sequence[i - 1] for i in seq_positions]


class ChoiceHoleRestriction(object):
    """
    Class to describe choice hole restrictions.

    :ivar permissible_combinations: variable of type ``Set[Tuple[int]]``, where
        the tuples are sorted sequences of hole numbers. If the set is not
        empty, then only such combinations are allowed.
    """
    DEFAULT_HOLE_SEPARATOR = ","
    DEFAULT_GROUP_SEPARATOR = ";"  # NB ";" trickier from Bash command line

    def __init__(
            self,
            # String-based init:
            description: str = "",
            hole_separator: str = DEFAULT_HOLE_SEPARATOR,
            group_separator: str = DEFAULT_GROUP_SEPARATOR,
            # Hole-based init:
            permissible_combinations: List[List[int]] = None) -> None:
        """
        Args:

            description: textual description like "1,3; 2,4" to restrict
                to the combinations of "hole 1 versus hole 3" and "hole 2 versus
                hole 4".

            hole_separator: string used to separate holes in a group
                (usually ",").

            group_separator: string used to separate groups
                (usually ";").

            permissible_combinations: list of lists of spatial hole numbers,
                as an alternative to using ``description``. Use one or the
                other.

        Raises:
            argparse.ArgumentTypeError: if its arguments are invalid.
        """
        def assert_hole_ok(hole_: int) -> None:
            if not (MIN_HOLE_NUMBER <= hole_ <= MAX_HOLE_NUMBER):
                raise ArgumentTypeError(
                    "Bad hole number {} (must be in range {}-{})".format(
                        hole_, MIN_HOLE_NUMBER, MAX_HOLE_NUMBER))

        if description and permissible_combinations:
            raise ArgumentTypeError(
                "Specify description or permissible_combinations, "
                "but not both"
            )
        permissible_combinations = permissible_combinations or []  # type: List[List[int]]  # noqa
        self.permissible_combinations = set()  # type: Set[Tuple[int]]
        # NOTE: can't add lists to a set (TypeError: unhashable type: 'list')
        if description:
            # Initialize from string
            for group_string in description.split(group_separator):
                holes = []  # type: List[int]
                for hole_string in group_string.split(hole_separator):
                    try:
                        hole = int(hole_string.strip())
                    except (ValueError, TypeError):
                        raise ArgumentTypeError("Not an integer: {!r}".format(
                            hole_string))
                    assert_hole_ok(hole)
                    holes.append(hole)
                if len(holes) != N_HOLES_FOR_CHOICE:
                    raise ArgumentTypeError(
                        "In description {!r}, hole group {!r} must be of "
                        "length {}, but isn't".format(
                            description, group_string, N_HOLES_FOR_CHOICE)
                    )
                holes.sort()
                self.permissible_combinations.add(tuple(holes))
        elif permissible_combinations:
            # Initialize from list of lists of holes
            for group in permissible_combinations:
                for hole in group:
                    if not isinstance(hole, int):
                        raise ArgumentTypeError(
                            "Not an integer: {!r}".format(hole))
                    assert_hole_ok(hole)
                holes = sorted(group)
                self.permissible_combinations.add(tuple(holes))
        # Check values are sensible:
        for holes in self.permissible_combinations:
            if len(holes) != len(set(holes)):
                raise ArgumentTypeError("No duplicates permitted; problem was "
                                        "{!r}".format(holes))

    def description(self) -> str:
        """
        Returns the description that can be used to recreate this object.
        """
        groupsep = self.DEFAULT_GROUP_SEPARATOR + " "
        holesep = self.DEFAULT_HOLE_SEPARATOR
        if self.permissible_combinations:
            return groupsep.join(
                holesep.join(str(h) for h in holes)
                for holes in sorted(self.permissible_combinations)
            )
        return ""

    def __str__(self) -> str:
        return "ChoiceHoleRestriction({!r})".format(self.description())

    def permissible(self, choice_holes: Iterable[int]) -> bool:
        """
        Is the supplied list of choice holes compatible with the restrictions?

        Args:
            choice_holes: list of spatial holes.
        """
        if not self.permissible_combinations:
            # No restrictions; OK
            return True
        sorted_holes = tuple(sorted(choice_holes))
        return sorted_holes in self.permissible_combinations


class ChoiceHoleRestrictionType(TypeDecorator):
    """
    SQLAlchemy data type to store :class:`.ChoiceHoleRestriction` in a
    database. See http://docs.sqlalchemy.org/en/latest/core/custom_types.html.
    """
    impl = String(length=MAX_HOLE_OR_SERIALPOS_PAIR_DEFINITION_STRING_LENGTH)

    def process_bind_param(
            self, value: Any,
            dialect: DefaultDialect) -> Optional[str]:
        """
        Converts a bound Python parameter to the database value.

        Args:
            value: should be a :class:`.ChoiceHoleRestriction` or None
            dialect: SQLAlchemy database dialect.

        Returns:
            string (outbound to database)
        """
        if not value:
            return value
        if not isinstance(value, ChoiceHoleRestriction):
            raise ValueError("Bad object arriving at "
                             "ChoiceHoleRestrictionType.process_bind_param: "
                             "{!r}".format(value))
        return value.description()

    def process_result_value(
            self, value: Any,
            dialect: DefaultDialect) -> Optional[ChoiceHoleRestriction]:
        """
        Receive a result-row column value to be converted.

        Args:

            value: data fetched from the database (will be a string).
            dialect: SQLAlchemy database dialect.

        Returns:

            a :class:`.ChoiceHoleRestriction` object if the string is valid
        """
        if not value:
            return None
        try:
            return ChoiceHoleRestriction(description=value)
        except ArgumentTypeError:
            log.debug("Bad value received from database to "
                      "ChoiceHoleRestrictionType.process_result_value: "
                      "{!r}".format(value))
            return None

    def process_literal_param(self, value: Any, dialect: DefaultDialect) -> str:
        """
        Receive a literal parameter value to be rendered inline within
        a statement.

        (An abstract method of ``TypeDecorator``, so we should implement it.)

        Args:
            value: a Python value
            dialect: SQLAlchemy database dialect.

        Returns:
            a string to be baked into some SQL
        """
        return str(value)

    @property
    def python_type(self) -> type:
        """
        Returns the Python type object expected to be returned by instances of
        this type, if known. It's :class:`.ChoiceHoleRestriction`.
        """
        return ChoiceHoleRestriction


class SerialPosRestriction(object):
    """
    Class to describe restrictions on the serial order positions offered at
    the choice phase.

    :ivar permissible_combinations: variable of type ``Set[Tuple[int]]``, where
        the tuples are sorted sequences of serial order position numbers (1
        being the first). If the set is not empty, then only such combinations
        are allowed.
    """
    DEFAULT_POS_SEPARATOR = ","
    DEFAULT_GROUP_SEPARATOR = ";"  # NB ";" trickier from Bash command line

    def __init__(
            self,
            # String-based init:
            description: str = "",
            position_separator: str = DEFAULT_POS_SEPARATOR,
            group_separator: str = DEFAULT_GROUP_SEPARATOR,
            # Hole-based init:
            permissible_combinations: List[List[int]] = None) -> None:
        """
        Args:

            description: textual description like "1,3; 2,3" to restrict
                to the combinations of "serial position 1 versus 3" and "serial
                position 2 versus 3".

            position_separator: string used to separate positions
                (usually ",").

            group_separator: string used to separate groups
                (usually ";").

            permissible_combinations: list of lists of serial order positions,
                as an alternative to using ``description``. Use one or the
                other.

        Raises:
            argparse.ArgumentTypeError: if its arguments are invalid.
        """
        def assert_position_ok(pos_: int) -> None:
            if not (MIN_SERIAL_ORDER_POSITION <= pos_ <=
                    MAX_SERIAL_ORDER_POSITION):
                raise ArgumentTypeError(
                    "Bad serial order position {} (must be in range "
                    "{}-{})".format(pos_, MIN_SERIAL_ORDER_POSITION,
                                    MAX_SERIAL_ORDER_POSITION))

        if description and permissible_combinations:
            raise ArgumentTypeError(
                "Specify description or permissible_combinations, "
                "but not both"
            )
        permissible_combinations = permissible_combinations or []  # type: List[List[int]]  # noqa
        self.permissible_combinations = set()  # type: Set[Tuple[int]]
        # NOTE: can't add lists to a set (TypeError: unhashable type: 'list')
        if description:
            # Initialize from string
            for group_string in description.split(group_separator):
                positions = []  # type: List[int]
                for pos_string in group_string.split(position_separator):
                    try:
                        pos = int(pos_string.strip())
                    except (ValueError, TypeError):
                        raise ArgumentTypeError("Not an integer: {!r}".format(
                            pos_string))
                    assert_position_ok(pos)
                    positions.append(pos)
                if len(positions) != N_HOLES_FOR_CHOICE:
                    raise ArgumentTypeError(
                        "In description {!r}, position group {!r} must be of "
                        "length {}, but isn't".format(
                            description, group_string, N_HOLES_FOR_CHOICE)
                    )
                positions.sort()
                self.permissible_combinations.add(tuple(positions))
        elif permissible_combinations:
            # Initialize from list of lists of holes
            for group in permissible_combinations:
                for pos in group:
                    if not isinstance(pos, int):
                        raise ArgumentTypeError(
                            "Not an integer: {!r}".format(pos))
                    assert_position_ok(pos)
                positions = sorted(group)
                self.permissible_combinations.add(tuple(positions))
        # Check values are sensible:
        for positions in self.permissible_combinations:
            if len(positions) != len(set(positions)):
                raise ArgumentTypeError("No duplicates permitted; problem was "
                                        "{!r}".format(positions))

    def description(self) -> str:
        """
        Returns the description that can be used to recreate this object.
        """
        groupsep = self.DEFAULT_GROUP_SEPARATOR + " "
        pos_sep = self.DEFAULT_POS_SEPARATOR
        if self.permissible_combinations:
            return groupsep.join(
                pos_sep.join(str(h) for h in holes)
                for holes in sorted(self.permissible_combinations)
            )
        return ""

    def __str__(self) -> str:
        return "SerialPosRestriction({!r})".format(self.description())

    def permissible(self, serial_positions: Iterable[int]) -> bool:
        """
        Is the supplied list of serial order position to be tested compatible
        with the restrictions?

        Args:
            serial_positions: the serial order positions to be presented in
                the choice phase
        """
        if not self.permissible_combinations:
            # No restrictions; OK
            return True
        sorted_positions = tuple(sorted(serial_positions))
        return sorted_positions in self.permissible_combinations


class SerialPosRestrictionType(TypeDecorator):
    """
    SQLAlchemy data type to store :class:`.SerialPosRestriction` in a
    database. See http://docs.sqlalchemy.org/en/latest/core/custom_types.html.
    """
    impl = String(length=MAX_HOLE_OR_SERIALPOS_PAIR_DEFINITION_STRING_LENGTH)

    def process_bind_param(
            self, value: Any,
            dialect: DefaultDialect) -> Optional[str]:
        """
        Converts a bound Python parameter to the database value.

        Args:
            value: should be a :class:`SerialPosRestriction` or None
            dialect: SQLAlchemy database dialect.

        Returns:
            string (outbound to database)
        """
        if not value:
            return value
        if not isinstance(value, SerialPosRestriction):
            raise ValueError(
                "Bad object arriving at "
                "SerialPosRestrictionType.process_bind_param: "
                "{!r}".format(value))
        return value.description()

    def process_result_value(
            self, value: Any,
            dialect: DefaultDialect) \
            -> Optional[SerialPosRestriction]:
        """
        Receive a result-row column value to be converted.

        Args:

            value: data fetched from the database (will be a string).
            dialect: SQLAlchemy database dialect.

        Returns:

            a :class:`.SerialPosRestriction` object if the string
            is valid
        """
        if not value:
            return None
        try:
            return SerialPosRestriction(description=value)
        except ArgumentTypeError:
            log.debug(
                "Bad value received from database to "
                "SerialPosRestrictionType.process_result_value: "
                "{!r}".format(value))
            return None

    def process_literal_param(self, value: Any, dialect: DefaultDialect) -> str:
        """
        Receive a literal parameter value to be rendered inline within
        a statement.

        (An abstract method of ``TypeDecorator``, so we should implement it.)

        Args:
            value: a Python value
            dialect: SQLAlchemy database dialect.

        Returns:
            a string to be baked into some SQL
        """
        return str(value)

    @property
    def python_type(self) -> type:
        """
        Returns the Python type object expected to be returned by instances of
        this type, if known. It's :class:`.SerialPosRestriction`.
        """
        return SerialPosRestriction


class TrialPlan(object):
    """
    Describes the planned sequence of holes to be offered, and then holes
    to be tested, for a single trial.

    :ivar sequence: sequence of 1-based hole numbers to be offered

    :ivar serial_order_choice: serial positions within the offered sequence to
        offer as choices (will be SORTED as they are offered simultaneously)

    :ivar hole_choice: hole positions to offer for the choice (will be SORTED
        as they are offered simultaneously)

    What's independent?

    - ``sequence`` and ``serial_order_choice`` are independent
    - ``sequence`` and ``correct_is_on_right`` are not independent
      (they are mediated by ``serial_order_choice``)
    - ``serial_order_choice`` and ``correct_is_on_right`` are not independent
      (they are mediated by ``sequence``)
    """
    def __init__(self, sequence: List[int],
                 serial_order_choice: List[int]) -> None:
        """
        Args:

            sequence: the sequence of hole numbers to be offered (e.g.
                [3, 4, 1] to present hole 3, hole 4, and hole 1 in that order).

            serial_order_choice: the serial order positions to be tested
                (e.g. [1, 3] for the first and third).
        """
        self.sequence = sequence  # type: List[int]
        self.serial_order_choice = sorted(serial_order_choice)
        self.hole_choice = sorted(
            serial_order_to_spatial(self.sequence, self.serial_order_choice))

    @property  # for debugging
    def correct_incorrect_holes(self) -> Tuple[int, int]:
        """
        Returns:
            tuple: ``(correct_hole, incorrect_hole)`` for the test phase.
        """
        serial_order_of_choice_holes = spatial_to_serial_order(
            self.sequence, self.hole_choice)
        if serial_order_of_choice_holes[0] < serial_order_of_choice_holes[1]:
            return self.hole_choice[0], self.hole_choice[1]
        else:
            return self.hole_choice[1], self.hole_choice[0]

    @property  # for debugging
    def correct_hole(self) -> int:
        """
        Returns:
            The correct hole number, from the test phase.
        """
        correct, incorrect = self.correct_incorrect_holes
        return correct

    @property  # for debugging
    def incorrect_hole(self) -> int:
        """
        Returns:
            The incorrect hole number, for the test phase.
        """
        correct, incorrect = self.correct_incorrect_holes
        return incorrect

    @property  # for debugging
    def correct_is_on_right(self) -> bool:
        """
        Returns:
             Is the correct hole on the right?
        """
        correct, incorrect = self.correct_incorrect_holes
        return correct > incorrect

    @property  # for debugging
    def sequence_length(self) -> int:
        """
        Returns:
            The length of the sequence presented.
        """
        return len(self.sequence)

    def __repr__(self) -> str:
        return (
            "TrialPlan(sequence={}, serial_order_choice={}, "
            "hole_choice={}; correct_hole={}, correct_is_on_right={})".format(
                self.sequence, self.serial_order_choice, self.hole_choice,
                self.correct_hole, self.correct_is_on_right)
        )

    # @property
    # def hole_serial_order_combo(self) -> List[int]:
    #     return self.serial_order_choice + self.hole_choice

    def meets_restrictions(
            self,
            choice_hole_restriction: ChoiceHoleRestriction = None,
            serial_pos_restriction: SerialPosRestriction = None) \
            -> bool:
        """
        Does the trial plan meet the specified restrictions?
        """
        if choice_hole_restriction:
            if not choice_hole_restriction.permissible(self.hole_choice):
                return False
        if serial_pos_restriction:
            if not serial_pos_restriction.permissible(
                    self.serial_order_choice):
                return False
        return True


# =============================================================================
# Program configuration
# =============================================================================

class Config(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``config`` table.
    """
    __tablename__ = 'config'

    config_id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    read_only = Column(Boolean)  # used for a live task, therefore can't edit
    stages = relationship("ConfigStage", order_by="ConfigStage.stagenum",
                          cascade="save-update, merge, delete")
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

    def __init__(self, **kwargs) -> None:
        """
        Must be clonable by deepcopy_sqla_object(), so must accept empty
        kwargs.
        """
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
        super().__init__(**kwargs)

    def __str__(self) -> str:
        return (
            "Config {config_id}: subject = {subject}, server = {server}, "
            "devicegroup = {devicegroup}".format(
                config_id=self.config_id,
                subject=self.subject,
                server=self.server,
                devicegroup=self.devicegroup,
            )
        )

    def get_modified_at_pretty(self) -> Optional[str]:
        """
        Gets the ``modified_at`` time as a human-readable string.
        """
        if self.modified_at is None:
            return None
        return self.modified_at.strftime(DATETIME_FORMAT_PRETTY)

    def clone(self, session: Session, read_only: bool = False) -> 'Config':
        """
        Makes a copy of itself and adds it to the specified SQLAlchemy session.

        Args:
            session: the SQLAlchemy session into which to insert the copy.
            read_only: sets the ``read_only`` property of the copy.

        Returns:
            the copy.
        """
        newconfig = deepcopy_sqla_object(self, session,
                                         flush=False)  # type: Config
        # ... will add to session
        newconfig.read_only = read_only
        session.flush()  # but not necessarily commit
        return newconfig

    def get_n_stages(self) -> int:
        """
        Returns the number of stages.
        """
        return len(self.stages)

    def has_stages(self) -> bool:
        """
        Does the config have at least one stage?
        """
        return self.get_n_stages() > 0


class ConfigStage(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``config_stage`` table.
    """
    __tablename__ = 'config_stage'

    config_stage_id = Column(Integer, primary_key=True)
    modified_at = Column(ArrowMicrosecondType,
                         default=arrow.now, onupdate=arrow.now)
    config_id = Column(Integer, ForeignKey('config.config_id'), nullable=False)
    stagenum = Column(Integer, nullable=False)  # consecutive, 1-based

    # Sequence
    sequence_length = Column(Integer)
    choice_hole_restriction = Column(ChoiceHoleRestrictionType, nullable=True)
    serial_pos_restriction = Column(SerialPosRestrictionType, nullable=True)
    side_dwor_multiplier = Column(Integer)
    # Limited hold
    limited_hold_s = Column(Float)
    # Progress to next stage when X of last Y correct, or total trials complete
    progression_criterion_x = Column(Integer)
    progression_criterion_y = Column(Integer)
    stop_after_n_trials = Column(Integer)

    def __init__(self, **kwargs) -> None:
        """
        Must be clonable by deepcopy_sqla_object(), so must accept empty
        kwargs.
        """
        self.config_id = kwargs.pop('config_id', None)  # type: int
        self.stagenum = kwargs.pop('stagenum', None)  # type: int
        self.choice_hole_restriction = kwargs.pop(
            'choice_hole_restriction', None)  # type: ChoiceHoleRestriction
        self.side_dwor_multiplier = kwargs.pop('side_dwor_multiplier', 1)
        self.sequence_length = kwargs.pop('sequence_length', None)  # type: int
        self.limited_hold_s = kwargs.pop('limited_hold_s', 10)  # type: float
        self.progression_criterion_x = kwargs.pop('progression_criterion_x',
                                                  10)  # type: int
        self.progression_criterion_y = kwargs.pop('progression_criterion_y',
                                                  12)  # type: int
        # In R: use binom.test(x, y) to get the p value for these.
        # Here, the defaults are such that progression requires p = 0.03857.
        self.stop_after_n_trials = kwargs.pop('stop_after_n_trials', 100)  # type: int  # noqa
        super().__init__(**kwargs)

    @property
    def choice_hole_restriction_desc(self) -> str:
        """
        Returns the description of any choice_hole_restriction.
        """
        if not self.choice_hole_restriction:
            return ""
        return self.choice_hole_restriction.description()

    @property
    def serial_pos_restriction_desc(self) -> str:
        """
        Returns the description of any serial_pos_restriction.
        """
        if not self.serial_pos_restriction:
            return ""
        return self.serial_pos_restriction.description()


# =============================================================================
# Session summary details
# =============================================================================

class TaskSession(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``session`` table (renamed from ``Session`` to
    ``TaskSession`` to avoid confusion with SQLAlchemy ``Session``).
    """
    __tablename__ = 'session'
    session_id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey('config.config_id'), nullable=False)
    config = relationship("Config")
    events = relationship("Event")
    trials = relationship("Trial")

    started_at = Column(ArrowMicrosecondType, nullable=False)
    software_version = Column(String(MAX_VERSION_LENGTH))
    filename = Column(Text)

    trials_responded = Column(Integer, nullable=False, default=0)
    trials_correct = Column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs) -> None:
        self.config_id = kwargs.pop('config_id')  # type: int
        self.started_at = kwargs.pop('started_at')  # type: arrow.Arrow
        self.trials_responded = 0
        self.trials_correct = 0
        self.software_version = SERIAL_ORDER_VERSION
        super().__init__(**kwargs)


# =============================================================================
# Trial details
# =============================================================================

class Trial(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``trial`` table.
    """
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

    def __init__(self, **kwargs) -> None:
        self.session_id = kwargs.pop('session_id', None)  # may be set later
        self.trialnum = kwargs.pop('trialnum')
        self.started_at = kwargs.pop('started_at')
        self.config_stage_id = kwargs.pop('config_stage_id')
        self.stagenum = kwargs.pop('stagenum')
        self.n_premature = 0
        self.sequence_n_offered = 0
        self.sequence_info = None  # current sequence info
        super().__init__(**kwargs)

    def set_sequence(self, sequence_holes: List[int]) -> None:
        """
        Sets the sequence for the first phase of the trial.

        Args:
            sequence_holes: ordered list of hole numbers.
        """
        self.sequence_holes = list(sequence_holes)  # make a copy
        self.sequence_length = len(sequence_holes)

    def set_choice(self, choice_holes: List[int]) -> None:
        """
        Sets the choice holes offered in the second phase of the trial.

        Args:
             choice_holes: a list, of length 2, of the hole numbers.
        """
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

    def get_sequence_holes_as_str(self) -> str:
        """
        Returns a CSV string of the sequence holes.
        """
        return ",".join(str(x) for x in self.sequence_holes)

    def get_choice_holes_as_str(self) -> str:
        """
        Returns a CSV string of the choice holes.
        """
        return ",".join(str(x) for x in self.choice_holes)

    def record_initiation(self, timestamp: arrow.Arrow) -> None:
        """
        Records the time of trial initiation.
        """
        self.initiated_at = timestamp
        self.initiation_latency_s = latency_s(self.started_at,
                                              self.initiated_at)

    def record_sequence_hole_lit(self, timestamp: arrow.Arrow,
                                 holenum: int) -> None:
        """
        Records the time and hole number that a sequence hole was illuminated.
        """
        self.sequence_n_offered += 1
        self.sequence_info = SequenceTiming(
            trial_id=self.trial_id,
            seq_pos=self.sequence_n_offered,
            hole_num=holenum,
        )
        self.sequence_info.record_hole_lit(timestamp)
        self.sequence_timings.append(self.sequence_info)

    def record_sequence_hole_response(self, timestamp: arrow.Arrow) -> None:
        """
        Records a response to a sequence hole.
        """
        if self.sequence_info is None:
            return
        self.sequence_info.record_hole_response(timestamp)

    def record_sequence_mag_lit(self, timestamp: arrow.Arrow) -> None:
        """
        Records illumination of the food magazine during the initial sequence.
        """
        if self.sequence_info is None:
            return
        self.sequence_info.record_mag_lit(timestamp)

    def record_sequence_mag_response(self, timestamp: arrow.Arrow) -> None:
        """
        Records a response to the food magazine during the initial sequence.
        """
        if self.sequence_info is None:
            return
        self.sequence_info.record_mag_response(timestamp)

    def record_choice_offered(self, timestamp: arrow.Arrow) -> None:
        """
        Records the time that the choice was offered.
        """
        self.choice_offered = True
        self.choice_offered_at = timestamp

    def record_response(self, response_hole: int,
                        timestamp: arrow.Arrow) -> bool:
        """
        Records the response during the choice phase.
        IMPLEMENTS THE KEY TASK RULE: "Which came first?"

        Args:
            response_hole: the hole that the subject responded to
            timestamp: when the response occurred
            was the response correct?
        """
        self.responded = True
        self.responded_at = timestamp
        self.responded_hole = response_hole
        self.response_latency_s = latency_s(self.choice_offered_at,
                                            self.responded_at)
        self.response_correct = response_hole == self.choice_hole_earliest
        return self.response_correct

    # noinspection PyUnusedLocal
    def record_premature(self, timestamp: arrow.Arrow) -> None:
        """
        Records a premature response.
        """
        self.n_premature += 1

    def record_reinforcement(self, timestamp: arrow.Arrow) -> None:
        """
        Records the delivery of reinforcement.
        """
        self.reinforced_at = timestamp

    def record_reinf_collection(self, timestamp: arrow.Arrow) -> None:
        """
        Records when the subject collected reinforcement.
        """
        if self.was_reinf_collected():
            return
        self.reinf_collected_at = timestamp
        self.reinf_collect_latency_s = latency_s(self.responded_at,
                                                 self.reinf_collected_at)

    def was_reinforced(self) -> bool:
        """
        Was the trial reinforced?
        """
        return self.reinforced_at is not None

    def was_reinf_collected(self) -> bool:
        """
        Was reinforcement collected?
        """
        return self.reinf_collected_at is not None

    def record_iti_start(self, timestamp: arrow.Arrow) -> None:
        """
        Records the time that the intertrial interval started.
        """
        self.iti_started_at = timestamp
        # And this one's done...
        self.sequence_info = None


# =============================================================================
# Event details
# =============================================================================

class Event(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``event`` table.
    """
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

    def __init__(self, **kwargs) -> None:
        self.session_id = kwargs.pop('session_id', None)  # may be set later
        self.eventnum_in_session = kwargs.pop('eventnum_in_session')
        self.trial_id = kwargs.pop('trial_id', None)
        self.trialnum = kwargs.pop('trialnum', None)
        self.eventnum_in_trial = kwargs.pop('eventnum_in_trial', None)
        self.event = kwargs.pop('event')
        self.timestamp = kwargs.pop('timestamp')
        self.whisker_timestamp_ms = kwargs.pop('whisker_timestamp_ms', None)
        self.from_server = kwargs.pop('from_server', False)
        super().__init__(**kwargs)


# =============================================================================
# Info/timings of the sequences, including response latencies
# =============================================================================

class SequenceTiming(SqlAlchemyAttrDictMixin, Base):
    """
    SQLAlchemy model for the ``sequence_timing`` table.
    """
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

    def __init__(self, **kwargs) -> None:
        self.trial_id = kwargs.pop('trial_id')
        self.seq_pos = kwargs.pop('seq_pos')
        self.hole_num = kwargs.pop('hole_num')
        super().__init__(**kwargs)

    def record_hole_lit(self, timestamp: arrow.Arrow) -> None:
        """
        Records that the hole has been illuminated.
        """
        self.hole_lit_at = timestamp

    def record_hole_response(self, timestamp: arrow.Arrow) -> None:
        """
        Records that the hole has been responded to.
        """
        self.hole_response_at = timestamp
        self.hole_response_latency_s = latency_s(self.hole_lit_at,
                                                 self.hole_response_at)

    def record_mag_lit(self, timestamp: arrow.Arrow) -> None:
        """
        Records that the food magazine has been illuminated.
        """
        self.mag_lit_at = timestamp

    def record_mag_response(self, timestamp: arrow.Arrow) -> None:
        """
        Records that the food magazine has been responded to.
        """
        self.mag_response_at = timestamp
        self.mag_response_latency_s = latency_s(self.mag_lit_at,
                                                self.mag_response_at)
