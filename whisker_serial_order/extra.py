#!/usr/bin/env python
# whisker_serial_order/extra.py


def latency_s(t1, t2):
    if t1 is None or t2 is None:
        return None
    delta = t2 - t1
    return delta.microseconds / 1000000
