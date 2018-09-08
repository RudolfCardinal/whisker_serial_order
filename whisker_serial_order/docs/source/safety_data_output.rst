..  docs/source/safety_data_output.rst.rst

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


Additional safety data output
=============================

As always, for safety, good Whisker tasks write their data to two places: the
database and a text file. In the brave new world of real databases and Python,
this task writes its data to the proper database ‘live’, so the database is
always up to date. When the task finishes, it reads that database and writes
both structure and data to a text file. It does so in SQL format, so that a
fully structured representation of all data relevant to a given session can
easily be regenerated simply by replaying the SQL output into a fresh database.

The directory used for these files is one of the following, in descending order
of priority: (1) the ``--outdir`` command-line parameter; (2) the
``WHISKER_SERIAL_ORDER_OUTDIR`` environment variable; (3) the current working
directory from which the task was started.
