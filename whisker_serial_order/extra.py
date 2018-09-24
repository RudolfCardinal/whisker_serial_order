#!/usr/bin/env python
# whisker_serial_order/extra.py

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

Additional functions.

"""

import datetime
import logging
from typing import Any, List, Optional, Union
import arrow

TimeType = Union[datetime.datetime, arrow.Arrow]

log = logging.getLogger(__name__)


def latency_s(t1: Optional[TimeType],
              t2: Optional[TimeType]) -> Optional[float]:
    """
    Calculates the latency in seconds between two datetime-type objects.

    Args:
        t1: start time
        t2: end time

    Returns:
        time difference in seconds, or ``None`` if either were ``None``
    """
    if t1 is None or t2 is None:
        return None
    delta = t2 - t1
    return delta.microseconds / 1000000


def enumerate_to_log(items: List[Any],
                     description: str = "",
                     start: int = 1,
                     linesep: str = "\n",
                     index_suffix: str = ". ",
                     loglevel: int = logging.DEBUG) -> None:
    r"""
    Describes a list to the log.

    Args:
        items: list of items
        start: index to start at (default 1)
        description: description
        linesep: line separator (default '\n')
        index_suffix: index suffix (default '. ')
        loglevel: log level
    """
    msg = description + linesep + linesep.join(
        "{index}{index_suffix}{item}".format(
            index=index,
            index_suffix=index_suffix,
            item=item
        )
        for index, item in enumerate(items, start=start)
    )
    log.log(loglevel, msg)
