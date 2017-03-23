#!/usr/bin/env python
# whisker_serial_order/extra.py

import datetime
from typing import Optional, Union
import arrow

TimeType = Union[datetime.datetime, arrow.Arrow]


def latency_s(t1: Optional[TimeType],
              t2: Optional[TimeType]) -> Optional[float]:
    if t1 is None or t2 is None:
        return None
    delta = t2 - t1
    return delta.microseconds / 1000000
