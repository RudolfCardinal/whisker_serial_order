..  docs/source/changelog.rst

..  Copyright © 2016-2018 Rudolf Cardinal (rudolf@pobox.com).
    .
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    .
        http://www.apache.org/licenses/LICENSE-2.0
    .
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.


Change history
==============

v0.1.0 – Feb–Mar 2016
---------------------

- Started. Released 21 Mar 2016.

Others, to v0.4.2
-----------------

- Not detailed in full.

v0.5.0 – Mar 2017
-----------------

- Changed from PySide to PyQt 5.8, following other projects (e.g. Starfeeder),
  as this is more stable and also allows Python 3.5.
- Added more test code (including command-line tests) for trial planning,
  following a query from YC, but this seems fine.

v0.6.0 – Sep 2018
-----------------

- Documentation from OpenOffice/PDF to Sphinx/HTML.

- Library upgrades:

  - ``alembic`` from 0.8.4 to 1.0.0
  - ``python-dateutil`` from 2.5.1 to 2.7.3
  - ``whisker`` from 1.0.0 to 1.1.0
  - ``SQLAlchemy`` from 1.2.0b2 to 1.2.12 (to fix ``Unknown system variable
    'tx_isolation'`` bug with MySQL 8.0.12)
  - ``sadisplay`` from 0.4.8 to 0.4.9
  - ``sqlalchemy-utils`` from 0.32.13 to 0.33.5

- Note that if you install MySQL Connector/Python system-wide (via the MySQL
  installer), it may not be available from a virtual environment; in that case,
  use ``pip install mysql-connector-python``.

- ``MAX_VERSION_LENGTH`` set to its proper value of 147.

- Options to restrict the choice holes offered. See
  :class:`whisker_serial_order.models.ChoiceHoleRestriction`. New field:
  ``config_stage.choice_hole_restriction``.

..  Veronika Zlatkina, McGill, 2018-09-10:
    - Typical sequence is of length 3.
    - McGill wish to restrict to specific test pair(s).
    VZ: yes, multiple pairs would be good.
    VZ: Counterbalance L/R.
    - Re omissions: causes problems for counterbalancing.
    - VZ suggestion: "Gellerman schedule" (sp?); e.g. in trials, 5 left, 5
    right, no more than 3 in a row.
    RNC suggestion: DWOR with DWOR multiplier instead.
    VZ: OK to forget about omissions for now.
    RNC: will need to think re fact that multiple things are involved in
    counterbalancing (sequence, serial order, correct side).
    VZ: counterbalancing

- Change to randomization method to prioritize "correct side" counterbalancing
  with DWOR mechanism. See
  :func:`whisker_serial_order.task.SerialOrderTask.create_trial_plans`. New
  field: ``config_stage.side_dwor_multiplier``.

- Cleanup of Alembic scripts, as per

  - https://bitbucket.org/zzzeek/alembic/issues/46/mysqltinyint-display_width-1-vs-saboolean
  - https://bitbucket.org/zzzeek/alembic/issues/374/alembic-detecs-type-change-from-tinyint

- Options to restrict the choice serial order position offered. See
  :class:`whisker_serial_order.models.SerialPosRestriction``. New field:
  ``config_stage.serial_pos_restriction``. Try this:

  .. code-block:: bash

    whisker_serial_order --testtrialplan --seqlen 4 --choice_hole_restriction "1,3" --serial_pos_restriction "1,2;3,4" --side_dwor_multiplier 3

- Docs at https://whiskerserialorder.readthedocs.io/

To do
=====

.. todolist::
