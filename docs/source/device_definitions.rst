..  docs/source/device_definitions.rst

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


Whisker device definitions
==========================

Within the task and its results, holes are numbered from 1–5. Existing Whisker
tasks (e.g. FiveChoice) use ``HOLE_0`` to ``HOLE_4`` and ``STIMLIGHT_0`` to
``STIMLIGHT_4``, so for backwards compatibility, we could use those; however,
that’s likely to be terribly confusing for anyone trying to debug this task. We
therefore provide new device names starting ``SO_`` (which can co-exist with old
names within one Whisker device definition file if necessary).

Inputs

.. code-block:: none

    SO_HOLE_1
    SO_HOLE_2
    SO_HOLE_3
    SO_HOLE_4
    SO_HOLE_5
    REARPANEL

Outputs:

.. code-block:: none

    SO_STIMLIGHT_1
    SO_STIMLIGHT_2
    SO_STIMLIGHT_3
    SO_STIMLIGHT_4
    SO_STIMLIGHT_5
    HOUSELIGHT
    PELLET
    MAGLIGHT
