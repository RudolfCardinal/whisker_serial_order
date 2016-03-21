#!/usr/bin/env python
# whisker_serial_order/constants.py

import os
import string
import sys

from attrdict import AttrDict

from .version import VERSION

LINESEP = "=" * 79

# =============================================================================
# Database stuff
# =============================================================================

ALEMBIC_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_CONFIG_FILENAME = 'alembic.ini'
DB_URL_ENV_VAR = "WHISKER_SERIAL_ORDER_DB_URL"
MSG_DB_ENV_VAR_NOT_SPECIFIED = """
{LINESEP}
You must specify the {var} environment variable (which is
an SQLAlchemy database URL), or pass it as a command-line argument. Examples
follow.

Windows:
    set {var}=mysql://username:password@localhost/database
Linux:
    export {var}=mysql://username:password@localhost/database
{LINESEP}
""".format(LINESEP=LINESEP, var=DB_URL_ENV_VAR)
WRONG_DATABASE_VERSION_STUB = string.Template("""
$LINESEP
Database revision should be {head_revision} but is {current_revision}.

- If the database version is too low, run the task with the
  "--upgrade-database" parameter (because your database is too old), or click
  the "Upgrade database" button in the GUI.

- If the database version is too high, upgrade the task (because you're
  trying to use an old task version with a newer database).
$LINESEP
""").substitute(LINESEP=LINESEP)

# =============================================================================
# File stuff
# =============================================================================

OUTPUT_DIR_ENV_VAR = "WHISKER_SERIAL_ORDER_OUTDIR"

# =============================================================================
# About
# =============================================================================

ABOUT = """
<b>Serial Order v{VERSION}</b><br>
<br>
Serial order task for Whisker (<a href="{WHISKER_URL}">{WHISKER_URL}</a>).<br>

You will also need:
<ul>
  <li>A database; see the manual for details. This task finds its database
  using either a command-line parameter or the environment variable
  {DB_URL_ENV_VAR}.</li>
  <li>Whisker.</li>
  <li>Suitable operant hardware, for real use.</li>
</ul>

By Rudolf Cardinal (rudolf@pobox.com).<br>
Copyright &copy; 2016 Rudolf Cardinal.
For licensing details see LICENSE.txt.
""".format(
    DB_URL_ENV_VAR=DB_URL_ENV_VAR,
    VERSION=VERSION,
    WHISKER_URL="http://www.whiskercontrol.com/",
)

DATETIME_FORMAT_PRETTY = "%Y-%m-%d %H:%M:%S"

# Where's the manual?
if getattr(sys, 'frozen', False):
    # Running inside a PyInstaller bundle.
    # http://pythonhosted.org/PyInstaller/#run-time-operation
    CURRENT_DIR = sys._MEIPASS
else:
    # Running in a normal Python environment.
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_FILENAME = os.path.join(CURRENT_DIR, 'MANUAL.pdf')


# =============================================================================
# Whisker devices (DI = digital in; DO = digital out)
# =============================================================================
# see http://www.whiskercontrol.com/help/FiveChoice.pdf

N_HOLES = 5
ALL_HOLE_NUMS = list(range(1, N_HOLES + 1))
# 1-based for task; 0-based for device definition file

DEV_DI = AttrDict({  # Digital inputs
    'MAGSENSOR': 'REARPANEL',
})
for h in ALL_HOLE_NUMS:
    DEV_DI["HOLE_{}".format(h)] = "SO_HOLE_{}".format(h)

DEV_DO = AttrDict({
    'HOUSELIGHT': 'HOUSELIGHT',
    'PELLET': 'PELLET',
    'MAGLIGHT': 'TRAYLIGHT',
})
for h in ALL_HOLE_NUMS:
    DEV_DO["STIMLIGHT_{}".format(h)] = "SO_STIMLIGHT_{}".format(h)

# =============================================================================
# Events
# =============================================================================

WEV = AttrDict({  # Whisker events (Whisker -> task)
    'MAGPOKE': 'mag_poke',
    'RESPONSE_1': 'response_hole_1',
    'RESPONSE_2': 'response_hole_2',
    'RESPONSE_3': 'response_hole_3',
    'RESPONSE_4': 'response_hole_4',
    'RESPONSE_5': 'response_hole_5',
    'REINF_END': 'reinf_end',
    'ITI_END': 'iti_end',
    'TIMEOUT_NO_RESPONSE_TO_LIGHT': 'timeout_no_response_to_light',
    'TIMEOUT_NO_RESPONSE_TO_MAG': 'timeout_no_response_to_mag',
    'TIMEOUT_NO_RESPONSE_TO_CHOICE': 'timeout_no_response_to_choice',
    'TIMEOUT_FOOD_UNCOLLECTED': 'timeout_food_uncollected',
    'SESSION_TIME_OVER': 'session_time_over',
})

TEV = AttrDict({  # Task events
    'SESSION_START': 'session_start',
    'SESSION_END': 'session_end',
    'TRIAL_START': 'trial_start',
    'TRIAL_END': 'trial_end',
    'PRESENT_LIGHT_1': 'present_light_1',
    'PRESENT_LIGHT_2': 'present_light_2',
    'PRESENT_LIGHT_3': 'present_light_3',
    'PRESENT_LIGHT_4': 'present_light_4',
    'PRESENT_LIGHT_5': 'present_light_5',
    'REQUIRE_MAGPOKE': 'require_magpoke',
    'PRESENT_CHOICE': 'present_choice',
    'ITI_START': 'iti_start',
    'REINFORCE': 'reinforce',
})

MAX_EVENT_LENGTH = 40

assert max(len(x) for x in TEV.values()) <= MAX_EVENT_LENGTH, (
    "Bug: MAX_EVENT_LENGTH is shorter than some values in TEV")
assert max(len(x) for x in WEV.values()) <= MAX_EVENT_LENGTH, (
    "Bug: MAX_EVENT_LENGTH is shorter than some values in WEV")
