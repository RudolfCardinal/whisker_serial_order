#!/usr/bin/env python
# whisker_serial_order/gui.py

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

Graphical user interface (GUI) classes for the serial order task.

"""

import argparse
import logging
import traceback
from typing import Any, Dict, Optional

from cardinal_pythonlib.process import launch_external_file
from cardinal_pythonlib.sqlalchemy.alembic_func import upgrade_database
from PyQt5.QtCore import (
    QEvent,
    QObject,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session  # for type hints
from whisker.exceptions import ValidationError
from whisker.qtclient import WhiskerOwner
from whisker.qt import (
    exit_on_exception,
    GenericAttrTableModel,
    GenericAttrTableView,
    StyledQGroupBox,
    TextLogElement,
    TransactionalDialog,
    TransactionalEditDialogMixin,
)
from whisker.sqlalchemy import database_is_sqlite, session_thread_scope
from whisker_serial_order.constants import (
    ABOUT,
    ALEMBIC_BASE_DIR,
    ALEMBIC_CONFIG_FILENAME,
    DOCUMENTATION_URL,
    N_HOLES,
    MSG_DB_ENV_VAR_NOT_SPECIFIED,
    WRONG_DATABASE_VERSION_STUB,
)
from whisker_serial_order.models import (
    ChoiceHoleRestriction,
    Config,
    ConfigStage,
    SerialPosRestriction,
)
from whisker_serial_order.task import SerialOrderTask

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

WINDOW_TITLE = 'Serial Order'


# =============================================================================
# Secondary GUI windows
# =============================================================================

class NoDatabaseSpecifiedWindow(QDialog):
    """
    Information dialogue: "no database specified".
    """
    exit_kill_log = pyqtSignal()

    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        info = QLabel(MSG_DB_ENV_VAR_NOT_SPECIFIED)
        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.exit_kill_log)
        ok_buttons.accepted.connect(self.accept)
        layout = QVBoxLayout()
        layout.addWidget(info)
        layout.addWidget(ok_buttons)
        self.setLayout(layout)

    # noinspection PyPep8Naming
    def closeEvent(self, event: QEvent) -> None:
        self.exit_kill_log.emit()
        event.accept()


class WrongDatabaseVersionWindow(QDialog):
    """
    Dialogue box to report "wrong database version" and offer to upgrade.
    """
    exit_kill_log = pyqtSignal()

    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self, current_revision: str, head_revision: str) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        info = QLabel(WRONG_DATABASE_VERSION_STUB.format(
            head_revision=head_revision,
            current_revision=current_revision))
        upgrade_button = QPushButton("Upgrade database")
        upgrade_button.clicked.connect(self.upgrade_database)
        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.exit_kill_log)
        ok_buttons.accepted.connect(self.accept)

        layout_upgrade = QHBoxLayout()
        layout_upgrade.addWidget(upgrade_button)
        layout_upgrade.addStretch()
        main_layout = QVBoxLayout()
        main_layout.addWidget(info)
        main_layout.addLayout(layout_upgrade)
        main_layout.addWidget(ok_buttons)
        self.setLayout(main_layout)

    # noinspection PyArgumentList
    @pyqtSlot()
    def upgrade_database(self) -> None:
        try:
            upgrade_database(ALEMBIC_CONFIG_FILENAME, ALEMBIC_BASE_DIR)
            # noinspection PyCallByClass,PyTypeChecker,PyArgumentList
            QMessageBox.about(self, "Success",
                              "Successfully upgraded database.")
        except Exception as e:
            # noinspection PyCallByClass,PyTypeChecker
            QMessageBox.about(
                self, "Failure",
                "Failed to upgrade database. Error was: {}".format(str(e)))

    # noinspection PyPep8Naming
    def closeEvent(self, event: QEvent) -> None:
        self.exit_kill_log.emit()
        event.accept()


# =============================================================================
# Models for table/list views
# =============================================================================

class ConfigTableModel(GenericAttrTableModel):
    """
    Qt model for tabular views of the :class:`.Config` class.
    """
    HEADINGS = [
        ("ID", "config_id"),
        ("Modified", "get_modified_at_pretty",),
        ("Subject", "subject"),
        ("Server", "server"),
        ("Port", "port"),
        ("Box", "devicegroup"),
        ("#Stages", "get_n_stages"),
    ]
    DEFAULT_SORT_COLUMN_NAME = "get_modified_at_pretty"

    def __init__(self, listdata, session: Session, **kwargs):
        super().__init__(
            data=listdata,
            header=self.HEADINGS,
            session=session,
            default_sort_column_name=self.DEFAULT_SORT_COLUMN_NAME,
            default_sort_order=Qt.DescendingOrder,
            **kwargs
        )


class ConfigStageTableModel(GenericAttrTableModel):
    """
    Qt model for tabular views of the :class:`.ConfigStage` class.
    """
    HEADINGS = [
        ("Stage#", "stagenum"),
        ("Seq.len.", "sequence_length"),
        ("Choice holes", "choice_hole_restriction_desc"),
        ("Serial pos", "serial_pos_restriction_desc"),
        ("Lim.hold(s)", "limited_hold_s"),
        ("Progress X", "progression_criterion_x",),
        ("Progress Y", "progression_criterion_y"),
        ("Stop N", "stop_after_n_trials"),
        ("Side DWOR mult.", "side_dwor_multiplier")
    ]
    DEFAULT_SORT_COLUMN_NAME = "get_modified_at_pretty"

    def __init__(self, listdata, session: Session, **kwargs):
        super().__init__(
            data=listdata,
            header=self.HEADINGS,
            session=session,
            **kwargs
        )


# =============================================================================
# Main GUI window
# =============================================================================

class MainWindow(QMainWindow):
    """
    Main GUI window.
    """
    # Don't inherit from QDialog, which has an additional Escape-to-close
    # function that's harder to trap. Use QWidget or QMainWindow.

    exit_kill_log = pyqtSignal()

    # noinspection PyArgumentList,PyUnresolvedReferences
    def __init__(self, dbsettings: Dict[str, Any]) -> None:
        super().__init__()
        self.dbsettings = dbsettings

        self.exit_pending = False
        self.db_is_sqlite = database_is_sqlite(dbsettings)
        self.whisker_task = None
        self.whisker_owner = None
        self.config_id = None
        self.task_running = False

        # ---------------------------------------------------------------------
        # GUI
        # ---------------------------------------------------------------------
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(400)

        config_group = StyledQGroupBox("Configure")
        config_layout = QHBoxLayout()
        self.configure_button = QPushButton('&Configure')
        self.configure_button.clicked.connect(self.configure)
        self.configure_msg = QLabel()
        self.configure_msg.setWordWrap(True)
        config_layout.addWidget(self.configure_button)
        config_layout.addWidget(self.configure_msg)
        config_layout.addStretch()
        config_group.setLayout(config_layout)

        run_group = StyledQGroupBox("Run")
        run_layout = QHBoxLayout()
        self.start_button = QPushButton('St&art')
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton('Sto&p')
        self.stop_button.clicked.connect(self.stop)
        run_layout.addWidget(self.start_button)
        run_layout.addWidget(self.stop_button)
        run_layout.addStretch()
        run_group.setLayout(run_layout)

        test_group = StyledQGroupBox("Testing and information")
        test_layout = QHBoxLayout()
        self.ping_whisker_button = QPushButton('&Ping Whisker')
        self.ping_whisker_button.clicked.connect(self.ping_whisker)
        help_button = QPushButton('&Help')
        help_button.clicked.connect(self.help)
        about_button = QPushButton('&About')
        about_button.clicked.connect(self.about)
        test_layout.addWidget(self.ping_whisker_button)
        test_layout.addWidget(help_button)
        test_layout.addWidget(about_button)
        test_layout.addStretch()
        test_group.setLayout(test_layout)

        status_group = StyledQGroupBox("Status")
        status_layout = QVBoxLayout()
        self.status_msg = QLabel()
        status_layout.addWidget(self.status_msg)
        status_group.setLayout(status_layout)

        self.log = TextLogElement()

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(config_group)
        main_layout.addWidget(run_group)
        main_layout.addWidget(test_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(self.log.get_widget())

        self.set_button_states()
        self.report("Not started.")
        self.report_selected_config()

    # -------------------------------------------------------------------------
    # Exiting
    # -------------------------------------------------------------------------

    # noinspection PyPep8Naming
    def closeEvent(self, event: QEvent) -> None:
        """Trap exit."""
        quit_msg = "Are you sure you want to exit?"
        # noinspection PyCallByClass,PyTypeChecker
        reply = QMessageBox.question(self, 'Really exit?', quit_msg,
                                     QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            event.ignore()
            return
        # "Really sure?"
        if self.task_running:
            quit_msg = ("A TASK IS RUNNING! Are you <b>really</b> sure "
                        "you want to exit?")
            # noinspection PyCallByClass,PyTypeChecker
            reply = QMessageBox.question(self, 'Really exit?', quit_msg,
                                         QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        # If subthreads aren't shut down, we get a segfault when we quit.
        # However, right now, signals aren't being processed because we're in
        # the GUI message loop. So we need to defer the call if subthreads are
        # running
        if not self.anything_running():
            self.exit_kill_log.emit()
            event.accept()  # actually quit
            return
        # Now stop everything
        log.warning("Waiting for threads to finish...")
        self.exit_pending = True
        if self.whisker_owner:
            self.whisker_owner.stop()
        # Will get a callback to whisker_owner_finished
        event.ignore()  # don't actually quit

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    # noinspection PyArgumentList
    @pyqtSlot()
    def configure(self) -> None:
        readonly = self.anything_running()
        with session_thread_scope(self.dbsettings, readonly) as session:
            w = ConfigPicker(session, readonly=readonly)
            self.config_id = w.exec_returning_config_id()
        self.report_selected_config()
        self.set_button_states()

    def report_selected_config(self) -> None:
        text = "<b>No config selected</b>"
        if self.config_id is not None:
            with session_thread_scope(self.dbsettings,
                                      readonly=True) as session:
                config = session.query(Config).get(self.config_id)
                if config is not None:
                    text = str(config)
        self.configure_msg.setText(text)

    # -------------------------------------------------------------------------
    # Task control
    # -------------------------------------------------------------------------

    # noinspection PyArgumentList
    @exit_on_exception
    @pyqtSlot()
    def start(self) -> None:
        if self.anything_running():
            # noinspection PyCallByClass,PyTypeChecker
            QMessageBox.about(self, "Can't start", "Already running.")
            return
        try:
            with session_thread_scope(self.dbsettings) as session:
                # Get the config
                editable_config = session.query(Config).get(self.config_id)
                # Make a frozen copy, which we then operate with
                frozen_config = editable_config.clone(session, read_only=True)
                session.commit()
                # The config object must be attached to a session to use
                # its attributes (without an explicit detach)
                self.config_id = frozen_config.config_id
                self.whisker_task = SerialOrderTask(self.dbsettings,
                                                    frozen_config.config_id)
                self.whisker_task.task_started_sig.connect(self.task_started)
                self.whisker_task.task_finished_sig.connect(self.task_finished)
                self.whisker_owner = WhiskerOwner(
                    self.whisker_task, frozen_config.server,
                    main_port=frozen_config.port, parent=self)
        except AttributeError as e:
            traceback.print_exc()
            log.debug("start: error: {}".format(e))
            # noinspection PyCallByClass,PyTypeChecker
            QMessageBox.about(self, "Can't start",
                              "Failed to start; config not set.")
            return
        self.report_selected_config()
        self.whisker_task.task_status_sig.connect(self.report)
        self.whisker_owner.status_sent.connect(self.status)
        self.whisker_owner.error_sent.connect(self.status)
        self.whisker_owner.finished.connect(self.whisker_owner_finished)
        self.whisker_owner.start()
        self.set_button_states()

    # noinspection PyArgumentList
    @pyqtSlot()
    def stop(self) -> None:
        if not self.anything_running():
            # noinspection PyCallByClass,PyTypeChecker
            QMessageBox.about(self, "Can't stop",
                              "Nothing to stop: not running.")
            return
        if self.task_running:
            quit_msg = ("A TASK IS RUNNING! Are you <b>really</b> sure "
                        "you want to stop?")
            # noinspection PyCallByClass,PyTypeChecker
            reply = QMessageBox.question(self, 'Really stop?', quit_msg,
                                         QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.status("Stopping...")
        if self.whisker_owner:
            self.whisker_owner.stop()
        self.set_button_states()

    # noinspection PyArgumentList
    @pyqtSlot()
    def whisker_owner_finished(self) -> None:
        self.status("Task finished")
        self.whisker_owner = None
        if self.exit_pending:
            # noinspection PyArgumentList
            QApplication.quit()
        self.report("Finished.")
        self.set_button_states()

    # noinspection PyArgumentList
    @pyqtSlot()
    def task_started(self) -> None:
        self.task_running = True
        self.status("Task now marked as BUSY.")

    def task_finished(self) -> None:
        self.task_running = False
        self.status("Task now marked as NOT BUSY.")

    def anything_running(self) -> bool:
        return (self.whisker_owner is not None and
                self.whisker_owner.is_running())

    def set_button_states(self) -> None:
        running = self.anything_running()
        self.configure_button.setText(
            'View configuration'
            if running and not self.db_is_sqlite else '&Configure')
        self.configure_button.setEnabled(not running or not self.db_is_sqlite)
        self.start_button.setEnabled(not running and
                                     self.config_id is not None)
        self.stop_button.setEnabled(running)
        self.ping_whisker_button.setEnabled(running)

    # -------------------------------------------------------------------------
    # Status log
    # -------------------------------------------------------------------------

    # noinspection PyArgumentList
    @pyqtSlot(str, str)
    def on_status(self, msg: str, source: str = "") -> None:
        # http://stackoverflow.com/questions/16568451
        if source:
            msg = "[{}] {}".format(source, msg)
        self.log.add(msg)

    def status(self, msg: str) -> None:
        self.on_status(msg, "main")

    # -------------------------------------------------------------------------
    # Status summary
    # -------------------------------------------------------------------------

    def report(self, msg: str) -> None:
        self.status_msg.setText(msg)

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------

    # noinspection PyArgumentList
    @pyqtSlot()
    def ping_whisker(self) -> None:
        if self.whisker_owner:
            self.whisker_owner.ping()

    # noinspection PyArgumentList
    @pyqtSlot()
    def about(self) -> None:
        # noinspection PyCallByClass,PyTypeChecker
        QMessageBox.about(self, WINDOW_TITLE, ABOUT)

    # noinspection PyArgumentList
    @pyqtSlot()
    def help(self) -> None:
        log.info("Help: launching {}".format(DOCUMENTATION_URL))
        launch_external_file(DOCUMENTATION_URL)
        self.status("Launched {}".format(DOCUMENTATION_URL))


# =============================================================================
# Choose a config
# =============================================================================

class ConfigPicker(TransactionalDialog):
    """
    Chooses a :class:`.Config` object.
    """

    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self, session: Session, parent: QObject = None,
                 readonly: bool = False) -> None:
        super().__init__(session=session, readonly=readonly, parent=parent)
        self.session = session
        self.readonly = readonly

        self.setWindowTitle("Choose configuration for Serial Order Task")

        instruction_1 = QLabel(
            "Select a config from the Editable list, then click OK.")

        editable_group = StyledQGroupBox('Editable configurations')
        editable_layout = QHBoxLayout()
        editable_button_layout = QVBoxLayout()
        self.ed_tv = GenericAttrTableView(session=self.session,
                                          modal_dialog_class=ConfigWindow,
                                          readonly=self.readonly)
        self.ed_tv.setMinimumWidth(650)
        editable_layout.addWidget(self.ed_tv)
        self.ed_edit_button = QPushButton("View" if readonly else "Edit")
        editable_button_layout.addWidget(self.ed_edit_button)
        self.ed_add_button = QPushButton("Add")
        editable_button_layout.addWidget(self.ed_add_button)
        self.ed_clone_button = QPushButton("Clone")
        editable_button_layout.addWidget(self.ed_clone_button)
        self.ed_delete_button = QPushButton("Delete")
        editable_button_layout.addWidget(self.ed_delete_button)
        editable_button_layout.addStretch()
        editable_layout.addLayout(editable_button_layout)
        editable_group.setLayout(editable_layout)

        instruction_2 = QLabel(
            "Once a config is used, a copy is frozen. You can view (and clone "
            "to the 'editable' list) but not use these directly.")

        readonly_group = StyledQGroupBox('Read-only copies (frozen)')
        readonly_layout = QHBoxLayout()
        readonly_button_layout = QVBoxLayout()
        self.ro_tv = GenericAttrTableView(session=self.session,
                                          modal_dialog_class=ConfigWindow,
                                          readonly=True)  # always readonly
        self.ro_tv.setMinimumWidth(650)
        readonly_layout.addWidget(self.ro_tv)
        self.ro_view_button = QPushButton("View")
        readonly_button_layout.addWidget(self.ro_view_button)
        self.ro_clone_button = QPushButton("Clone")
        readonly_button_layout.addWidget(self.ro_clone_button)
        readonly_button_layout.addStretch()
        readonly_layout.addLayout(readonly_button_layout)
        readonly_group.setLayout(readonly_layout)

        ok_cancel_layout = QHBoxLayout()
        ok_cancel_layout.addStretch()
        cancel_button = QPushButton("&Cancel")
        cancel_button.clicked.connect(self.reject)
        ok_cancel_layout.addWidget(cancel_button)
        self.ok_button = QPushButton("&OK")
        self.ok_button.clicked.connect(self.accept)
        ok_cancel_layout.addWidget(self.ok_button)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(instruction_1)
        main_layout.addWidget(editable_group)
        main_layout.addWidget(instruction_2)
        main_layout.addWidget(readonly_group)
        main_layout.addLayout(ok_cancel_layout)

        self.ed_tv.selection_changed.connect(self.set_ed_button_states)
        self.ed_edit_button.clicked.connect(self.edit_view_ed)
        self.ed_add_button.clicked.connect(self.add_ed)
        self.ed_clone_button.clicked.connect(self.clone_ed)
        self.ed_delete_button.clicked.connect(self.delete_ed)

        self.ro_tv.selection_changed.connect(self.set_ro_button_states)
        self.ro_view_button.clicked.connect(self.view_ro)
        self.ro_clone_button.clicked.connect(self.clone_ro)

        self.set_ed_button_states()
        self.set_ro_button_states()

    def exec_(self) -> int:
        # http://stackoverflow.com/questions/18998010/flake8-complains-on-boolean-comparison-in-filter-clause  # noqa
        ro_configs = self.session.query(Config).filter(
            Config.read_only == False).all()  # noqa
        ed_configs = self.session.query(Config).filter(
            Config.read_only == True).all()  # noqa
        ro_model = ConfigTableModel(ro_configs, self.session)
        ed_model = ConfigTableModel(ed_configs, self.session, deletable=False)
        self.ed_tv.setModel(ro_model)
        self.ro_tv.setModel(ed_model)
        return super().exec_()

    def exec_returning_config_id(self) -> Optional[int]:
        result = self.exec_()
        if result != QDialog.Accepted:
            return None
        obj = self.ed_tv.get_selected_object()  # type: Optional[Config]
        if obj is None:
            return
        return obj.config_id

    def set_ed_button_states(self) -> None:
        selected = self.ed_tv.is_selected()
        self.ed_edit_button.setEnabled(selected)
        self.ed_add_button.setEnabled(not self.readonly)
        self.ed_clone_button.setEnabled(selected and not self.readonly)
        self.ed_delete_button.setEnabled(selected and not self.readonly)
        self.ok_button.setEnabled(selected)

    def set_ro_button_states(self) -> None:
        selected = self.ro_tv.is_selected()
        self.ro_view_button.setEnabled(selected)
        self.ro_clone_button.setEnabled(selected and not self.readonly)

    def delete_ed(self) -> None:
        self.ed_tv.remove_selected()

    def add_ed(self) -> None:
        # TO ADD IMMEDIATELY WITHOUT VALIDATION:
        # self.ed_tv.insert_at_start(Config(), add_to_session=True)
        # TO ADD/VALIDATE TRANSACTIONALLY:
        self.ed_tv.add_in_nested_transaction(Config())

    def edit_view_ed(self) -> None:
        self.ed_tv.edit_selected()

    def view_ro(self) -> None:
        self.ro_tv.edit_selected()

    def clone_ed(self) -> None:
        obj = self.ed_tv.get_selected_object()  # type: Optional[Config]
        if obj is None:
            return
        newobj = obj.clone(self.session, read_only=False)
        self.ed_tv.insert_at_start(newobj, add_to_session=True)
        # ... OK to add something to a session twice

    def clone_ro(self) -> None:
        obj = self.ro_tv.get_selected_object()  # type: Optional[Config]
        if obj is None:
            return
        newobj = obj.clone(self.session, read_only=False)
        # Ensure it is NOT read-only, and add it to the EDITABLE list.
        self.ed_tv.insert_at_start(newobj, add_to_session=True)


# =============================================================================
# Edit main config
# ============================================================================

class ConfigWindow(TransactionalEditDialogMixin, QDialog):
    """
    Edits a :class:`.Config` object.
    """

    # noinspection PyUnresolvedReferences,PyArgumentList
    def __init__(self, session: Session, config: Config,
                 parent: QObject = None, readonly: bool = False) -> None:
        main_layout = QVBoxLayout()
        super().__init__(parent=parent,  # QDialog
                         session=session,  # TransactionalEditDialogMixin,
                         obj=config,  # TransactionalEditDialogMixin
                         layout=main_layout,  # TransactionalEditDialogMixin
                         readonly=readonly)  # TransactionalEditDialogMixin
        self.session = session

        # Title
        self.setWindowTitle("Configure Serial Order Task")

        # Elements
        self.server_edit = QLineEdit(placeholderText="typically: localhost")
        self.port_edit = QLineEdit(placeholderText="typically: 3233")
        self.devicegroup_edit = QLineEdit(placeholderText="typically: box<n>")
        self.subject_edit = QLineEdit(placeholderText="e.g. name/code")
        self.reinf_n_pellets_edit = QLineEdit(placeholderText="e.g. 2")
        self.reinf_pellet_pulse_ms_edit = QLineEdit(placeholderText="e.g. 45")
        self.reinf_interpellet_gap_ms_edit = QLineEdit(
            placeholderText="e.g. 250")
        self.iti_edit = QLineEdit(placeholderText="e.g. 2000")
        self.repeat_incomplete_check = QCheckBox()
        self.session_time_limit_edit = QLineEdit(placeholderText="e.g. 60")
        self.stages_lv = GenericAttrTableView(
            session=self.session,
            modal_dialog_class=StageConfigDialog,
            sortable=False,
            readonly=readonly)
        self.stages_lv.selected_maydelete.connect(
            self.set_stages_button_states)
        self.stages_lv.setMinimumWidth(750)

        # Layout/buttons
        whisker_group = StyledQGroupBox('Whisker')
        whisker_form = QFormLayout()
        whisker_form.addRow("Server", self.server_edit)
        whisker_form.addRow("Port", self.port_edit)
        whisker_form.addRow("Device group (box)", self.devicegroup_edit)
        whisker_group.setLayout(whisker_form)

        subject_group = StyledQGroupBox('Subject')
        subject_form = QFormLayout()
        subject_form.addRow("Subject", self.subject_edit)
        subject_group.setLayout(subject_form)

        reinf_group = StyledQGroupBox('Reinforcer')
        reinf_form = QFormLayout()
        reinf_form.addRow("# Pellets per reinforcer",
                          self.reinf_n_pellets_edit)
        reinf_form.addRow("Pellet dispenser pulse time (ms)",
                          self.reinf_pellet_pulse_ms_edit)
        reinf_form.addRow("Interpellet gap (ms)",
                          self.reinf_interpellet_gap_ms_edit)
        reinf_group.setLayout(reinf_form)

        trial_group = StyledQGroupBox('Trial settings')
        trial_form = QFormLayout()
        trial_form.addRow("Intertrial interval (ITI) duration (ms)",
                          self.iti_edit)
        trial_form.addRow("Repeat incomplete trials",
                          self.repeat_incomplete_check)
        trial_group.setLayout(trial_form)

        overall_limits_group = StyledQGroupBox('Overall limits')
        overall_limits_form = QFormLayout()
        overall_limits_form.addRow("Overall session time limit (min)",
                                   self.session_time_limit_edit)
        overall_limits_group.setLayout(overall_limits_form)

        stages_group = StyledQGroupBox('Stages')
        stages_layout_1 = QHBoxLayout()
        stages_layout_2 = QVBoxLayout()
        self.stages_add_button = QPushButton('Add')
        self.stages_add_button.clicked.connect(self.add_stage)
        self.stages_add_button.setEnabled(not readonly)
        self.stages_remove_button = QPushButton('Remove')
        self.stages_remove_button.clicked.connect(self.remove_stage)
        self.stages_remove_button.setEnabled(not readonly)
        self.stages_edit_button = QPushButton('View' if readonly else 'Edit')
        self.stages_edit_button.clicked.connect(self.edit_stage)
        self.stages_up_button = QPushButton('Up')
        self.stages_up_button.clicked.connect(self.stage_up)
        self.stages_down_button = QPushButton('Down')
        self.stages_down_button.clicked.connect(self.stage_down)
        stages_layout_2.addWidget(self.stages_add_button)
        stages_layout_2.addWidget(self.stages_remove_button)
        stages_layout_2.addWidget(self.stages_edit_button)
        stages_layout_2.addWidget(self.stages_up_button)
        stages_layout_2.addWidget(self.stages_down_button)
        stages_layout_2.addStretch()
        stages_layout_1.addWidget(self.stages_lv)
        stages_layout_1.addLayout(stages_layout_2)
        stages_group.setLayout(stages_layout_1)

        main_layout.addWidget(whisker_group)
        main_layout.addWidget(subject_group)
        main_layout.addWidget(reinf_group)
        main_layout.addWidget(trial_group)
        main_layout.addWidget(overall_limits_group)
        main_layout.addWidget(stages_group)

        self.set_stages_button_states(False, False)

        # Pass in data
        self.object_to_dialog(self.obj)

    # noinspection PyArgumentList
    @pyqtSlot(bool, bool)
    def set_stages_button_states(self, selected: bool,
                                 maydelete: bool) -> None:
        if not self.readonly:
            self.stages_remove_button.setEnabled(maydelete)
        self.stages_edit_button.setEnabled(selected)
        self.stages_up_button.setEnabled(selected and not self.readonly)
        self.stages_down_button.setEnabled(selected and not self.readonly)

    def add_stage(self) -> None:
        config = ConfigStage(config_id=self.obj.config_id,
                             stagenum=self.obj.get_n_stages() + 1)
        self.stages_lv.add_in_nested_transaction(config)
        self.renumber_refresh()

    def remove_stage(self) -> None:
        self.stages_lv.remove_selected()
        self.renumber_refresh()

    def edit_stage(self) -> None:
        self.stages_lv.edit_selected()

    def stage_up(self) -> None:
        self.stages_lv.move_selected_up()
        self.renumber_refresh()

    def stage_down(self) -> None:
        self.stages_lv.move_selected_down()
        self.renumber_refresh()

    def renumber_refresh(self) -> None:
        for i, stage in enumerate(self.obj.stages):
            stage.stagenum = i + 1
        self.session.flush()

    def object_to_dialog(self, obj: Config) -> None:
        self.server_edit.setText(obj.server)
        self.port_edit.setText(str(obj.port or ''))
        self.devicegroup_edit.setText(obj.devicegroup)
        self.subject_edit.setText(obj.subject)
        self.reinf_n_pellets_edit.setText(str(obj.reinf_n_pellets or ''))
        self.reinf_pellet_pulse_ms_edit.setText(
            str(obj.reinf_pellet_pulse_ms or ''))
        self.reinf_interpellet_gap_ms_edit.setText(
            str(obj.reinf_interpellet_gap_ms or ''))
        self.iti_edit.setText(str(obj.iti_duration_ms or ''))
        self.repeat_incomplete_check.setChecked(
            obj.repeat_incomplete_trials or False)
        self.session_time_limit_edit.setText(str(
            obj.session_time_limit_min or ''))

        stages_lm = ConfigStageTableModel(obj.stages, self.session)
        self.stages_lv.setModel(stages_lm)

    def dialog_to_object(self, obj: Config) -> None:
        # Master config validation and cross-checks.
        # ---------------------------------------------------------------------
        # Basic checks
        # ---------------------------------------------------------------------
        self.renumber_refresh()
        try:
            obj.server = self.server_edit.text()
            assert len(obj.server) > 0
        except AssertionError:
            raise ValidationError("Invalid server name")
        try:
            obj.port = int(self.port_edit.text())
            assert obj.port > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid port number")
        try:
            obj.devicegroup = self.devicegroup_edit.text()
            assert len(obj.devicegroup) > 0
        except AssertionError:
            raise ValidationError("Invalid device group name")

        try:
            obj.subject = self.subject_edit.text()
            assert len(obj.subject) > 0
        except AssertionError:
            raise ValidationError("Invalid subject name")

        try:
            obj.reinf_n_pellets = int(self.reinf_n_pellets_edit.text())
            assert obj.reinf_n_pellets > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid # pellets")
        try:
            obj.reinf_pellet_pulse_ms = int(
                self.reinf_pellet_pulse_ms_edit.text())
            assert obj.reinf_pellet_pulse_ms > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid pellet pulse time")
        try:
            obj.reinf_interpellet_gap_ms = int(
                self.reinf_interpellet_gap_ms_edit.text())
            assert obj.reinf_interpellet_gap_ms > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid interpellet gap")

        try:
            obj.iti_duration_ms = int(self.iti_edit.text())
            assert obj.iti_duration_ms > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid ITI duration")
        obj.repeat_incomplete_trials = self.repeat_incomplete_check.isChecked()

        try:
            obj.session_time_limit_min = float(
                self.session_time_limit_edit.text())
            assert obj.session_time_limit_min > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid session time limit (must be >0)")

        try:
            assert obj.has_stages()
        except AssertionError:
            raise ValidationError("No stages specified")


# =============================================================================
# Edit stage
# =============================================================================

class StageConfigDialog(TransactionalEditDialogMixin, QDialog):
    """
    Edits a :class:`.ConfigStage` object.
    """

    # noinspection PyArgumentList
    def __init__(self, session: Session, stage: ConfigStage,
                 parent: QObject = None, readonly: bool = False) -> None:
        main_layout = QVBoxLayout()
        super().__init__(parent=parent,  # QDialog
                         session=session,  # TransactionalEditDialogMixin
                         obj=stage,  # TransactionalEditDialogMixin
                         layout=main_layout,  # TransactionalEditDialogMixin
                         readonly=readonly)  # TransactionalEditDialogMixin

        self.setWindowTitle("Configure stage")

        self.seqlen_edit = QLineEdit(placeholderText="range 2-5")
        self.choice_restriction_edit = QLineEdit(
            placeholderText="e.g. 1,2;3,5 to restrict to holes 1+2 and 3+5")
        self.serial_pos_restriction_edit = QLineEdit(
            placeholderText="e.g. 1,2;2,3 to restrict to serial positions "
                            "1v2 and 2v3")
        self.side_dwor_multiplier_edit = QLineEdit(
            placeholderText="Integer >= 1. See documentation!")
        self.limhold_edit = QLineEdit(placeholderText="must be >0")
        self.progress_x_edit = QLineEdit(placeholderText="specify X")
        self.progress_y_edit = QLineEdit(placeholderText="specify Y")
        self.stop_n_edit = QLineEdit(placeholderText="specify N")

        sequence_group = StyledQGroupBox('Sequence')
        sequence_form = QFormLayout()
        sequence_form.addRow("Sequence length", self.seqlen_edit)
        sequence_form.addRow("Optional restrictions on choice holes",
                             self.choice_restriction_edit)
        sequence_form.addRow(
            "Optional restrictions on serial position combinations tested",
            self.serial_pos_restriction_edit)
        sequence_form.addRow(
            "Draw-without-replacement (DWOR) multiplier for<br>"
            "counterbalancing correct L/R side",
            self.side_dwor_multiplier_edit)
        sequence_group.setLayout(sequence_form)

        limhold_group = StyledQGroupBox('Limited hold')
        limhold_form = QFormLayout()
        limhold_form.addRow("Limited hold (s)", self.limhold_edit)
        limhold_group.setLayout(limhold_form)

        progression_group = StyledQGroupBox('Progression/termination')
        progression_form = QFormLayout()
        progression_form.addRow("Progress after X...", self.progress_x_edit)
        progression_form.addRow("... of last Y trials correct",
                                self.progress_y_edit)
        progression_form.addRow("Stop after N trials", self.stop_n_edit)
        progression_group.setLayout(progression_form)

        main_layout.addWidget(sequence_group)
        main_layout.addWidget(limhold_group)
        main_layout.addWidget(progression_group)

        # Pass in data
        self.object_to_dialog(self.obj)

    def object_to_dialog(self, obj: ConfigStage) -> None:
        self.seqlen_edit.setText(str(obj.sequence_length or ''))
        self.choice_restriction_edit.setText(obj.choice_hole_restriction_desc)
        self.serial_pos_restriction_edit.setText(
            obj.serial_pos_restriction_desc)
        self.side_dwor_multiplier_edit.setText(
            str(obj.side_dwor_multiplier or ''))
        self.limhold_edit.setText(str(obj.limited_hold_s or ''))
        self.progress_x_edit.setText(str(obj.progression_criterion_x or ''))
        self.progress_y_edit.setText(str(obj.progression_criterion_y or ''))
        self.stop_n_edit.setText(str(obj.stop_after_n_trials or ''))

    def dialog_to_object(self, obj: ConfigStage) -> None:
        try:
            obj.sequence_length = int(self.seqlen_edit.text())
            assert 2 <= obj.sequence_length <= N_HOLES
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid sequence length")

        try:
            cr_text = self.choice_restriction_edit.text()
            obj.choice_hole_restriction = (
                ChoiceHoleRestriction(cr_text) if cr_text else None
            )
        except argparse.ArgumentTypeError:
            raise ValidationError("Invalid choice hole restriction")

        try:
            sp_text = self.serial_pos_restriction_edit.text()
            obj.serial_pos_restriction = (
                SerialPosRestriction(sp_text) if sp_text else None
            )
        except argparse.ArgumentTypeError:
            raise ValidationError("Invalid serial position restriction")

        try:
            obj.side_dwor_multiplier = int(
                self.side_dwor_multiplier_edit.text())
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid DWOR multiplier")

        try:
            obj.limited_hold_s = float(self.limhold_edit.text())
            assert obj.limited_hold_s > 0
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid limited hold")

        try:
            obj.progression_criterion_x = int(self.progress_x_edit.text())
            assert obj.progression_criterion_x >= 1
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid X")

        try:
            obj.progression_criterion_y = int(self.progress_y_edit.text())
            assert obj.progression_criterion_y >= 1
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid Y")

        try:
            assert obj.progression_criterion_x <= obj.progression_criterion_y
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Must have: X <= Y")

        try:
            obj.stop_after_n_trials = int(self.stop_n_edit.text())
            assert obj.stop_after_n_trials >= 1
        except (AssertionError, TypeError, ValueError):
            raise ValidationError("Invalid N")
