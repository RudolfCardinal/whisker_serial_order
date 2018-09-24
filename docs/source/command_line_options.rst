..  docs/source/command_line_options.rst

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


Command-line options
====================

Command-line options as of 2018-09-09:

.. code-block:: none

    usage: whisker_serial_order [-h] [--logfile LOGFILE] [--verbose] [--guilog]
                                [--upgrade-database] [--dburl DBURL] [--dbecho]
                                [--outdir OUTDIR] [--gui] [--schema] [--java JAVA]
                                [--plantuml PLANTUML] [--schemastem SCHEMASTEM]
                                [--testtrialplan] [--seqlen SEQUENCE_LEN]
                                [--choice_hole_restriction TEST_HOLE_GROUPS]

    whisker_serial_order v0.6.0. Serial order task for Whisker.

    optional arguments:
      -h, --help            show this help message and exit
      --logfile LOGFILE     Filename to append log to
      --verbose, -v         Be verbose. (Use twice for extra verbosity.)
      --guilog              Show Python log in a GUI window
      --upgrade-database    Upgrade database to current version.
      --dburl DBURL         Database URL (if not specified, task will look in
                            WHISKER_SERIAL_ORDER_DB_URL environment variable).
      --dbecho              Echo SQL to log.
      --outdir OUTDIR       Directory for output file (if not specified, task will
                            look in WHISKER_SERIAL_ORDER_OUTDIR environment
                            variable, or if none, working directory).
      --gui, -g             GUI mode only
      --schema              Generate schema picture and stop
      --java JAVA           Java executable (for schema diagrams); default is
                            'java'
      --plantuml PLANTUML   PlantUML Java .jar file (for schema diagrams); default
                            is 'plantuml.jar'
      --schemastem SCHEMASTEM
                            Stem for output filenames (for schema diagrams);
                            default is 'schema'; '.plantuml' and '.png' are
                            appended
      --testtrialplan       Print a test trial plan of the specified sequence
                            length +/- restrictions
      --seqlen SEQUENCE_LEN
                            Sequence length for --testtrialplan
      --choice_hole_restriction CHOICE_HOLE_GROUPS
                            Optional choice hole restrictions for --testtrialplan;
                            use e.g. '--choice_hole_restriction "1,2;3,4"' to
                            restrict the choice phase to holes 1 v 2 and 3 v 4
