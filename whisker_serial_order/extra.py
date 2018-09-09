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
from typing import Optional, Union
import arrow

TimeType = Union[datetime.datetime, arrow.Arrow]


def latency_s(t1: Optional[TimeType],
              t2: Optional[TimeType]) -> Optional[float]:
    """
    Calculates the latency in seconds between two datetime-type objects.

    :param t1: start time
    :param t2: end time
    :return: time difference in seconds, or ``None`` if either were ``None``
    """
    if t1 is None or t2 is None:
        return None
    delta = t2 - t1
    return delta.microseconds / 1000000
