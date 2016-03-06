#!/usr/bin/env python
# whisker_serial_order/gui.py

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import traceback

from PySide.QtCore import Qt, Slot
from PySide.QtGui import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextCursor,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from whisker.exceptions import ValidationError
from whisker.qtclient import WhiskerOwner
from whisker.qtsupport import (
    exit_on_exception,
    GenericAttrTableModel,
    GenericAttrTableView,
    StyledQGroupBox,
    TransactionalDialog,
    TransactionalEditDialogMixin,
)
from whisker.sqlalchemysupport import (
    database_is_sqlite,
    session_thread_scope,
    upgrade_database,
)

from .constants import (
    ABOUT,
    ALEMBIC_BASE_DIR,
    ALEMBIC_CONFIG_FILENAME,
    MSG_DB_ENV_VAR_NOT_SPECIFIED,
    WRONG_DATABASE_VERSION_STUB,
)
from .models import Config
from .task import SerialOrderTask

# =============================================================================
# Constants
# =============================================================================

WINDOW_TITLE = 'Serial Order'


# =============================================================================
# Secondary GUI windows
# =============================================================================

class NoDatabaseSpecifiedWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        info = QLabel(MSG_DB_ENV_VAR_NOT_SPECIFIED)
        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.accept)
        layout = QVBoxLayout()
        layout.addWidget(info)
        layout.addWidget(ok_buttons)
        self.setLayout(layout)


class WrongDatabaseVersionWindow(QDialog):
    def __init__(self, current_revision, head_revision):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)

        info = QLabel(WRONG_DATABASE_VERSION_STUB.format(
            head_revision=head_revision,
            current_revision=current_revision))
        upgrade_button = QPushButton("Upgrade database")
        upgrade_button.clicked.connect(self.upgrade_database)
        ok_buttons = QDialogButtonBox(QDialogButtonBox.Ok,
                                      Qt.Horizontal, self)
        ok_buttons.accepted.connect(self.accept)

        layout_upgrade = QHBoxLayout()
        layout_upgrade.addWidget(upgrade_button)
        layout_upgrade.addStretch()
        main_layout = QVBoxLayout()
        main_layout.addWidget(info)
        main_layout.addLayout(layout_upgrade)
        main_layout.addWidget(ok_buttons)
        self.setLayout(main_layout)

    @Slot()
    def upgrade_database(self):
        try:
            upgrade_database(ALEMBIC_CONFIG_FILENAME, ALEMBIC_BASE_DIR)
            QMessageBox.about(self, "Success",
                              "Successfully upgraded database.")
        except Exception as e:
            QMessageBox.about(
                self, "Failure",
                "Failed to upgrade database. Error was: {}".format(str(e)))


# =============================================================================
# Main GUI window
# =============================================================================

class MainWindow(QMainWindow):
    # Don't inherit from QDialog, which has an additional Escape-to-close
    # function that's harder to trap. Use QWidget or QMainWindow.

    def __init__(self, dbsettings):
        super().__init__()
        self.dbsettings = dbsettings

        self.exit_pending = False
        self.db_is_sqlite = database_is_sqlite(dbsettings)
        self.whisker_task = None
        self.whisker_owner = None
        self.config_id = None

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

        # For nested layouts: (1) create everything, (2) lay out
        log_group = StyledQGroupBox("Log")
        log_layout_1 = QVBoxLayout()
        log_layout_2 = QHBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.NoWrap)
        font = self.log.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        log_clear_button = QPushButton('Clear log')
        log_clear_button.clicked.connect(self.log.clear)
        log_copy_button = QPushButton('Copy to clipboard')
        log_copy_button.clicked.connect(self.copy_whole_log)
        log_layout_2.addWidget(log_clear_button)
        log_layout_2.addWidget(log_copy_button)
        log_layout_2.addStretch()
        log_layout_1.addWidget(self.log)
        log_layout_1.addLayout(log_layout_2)
        log_group.setLayout(log_layout_1)

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(config_group)
        main_layout.addWidget(run_group)
        main_layout.addWidget(test_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(log_group)

        self.set_button_states()
        self.report("Not started.")
        self.report_selected_config()

    # -------------------------------------------------------------------------
    # Exiting
    # -------------------------------------------------------------------------

    def closeEvent(self, event):
        """Trap exit."""
        quit_msg = "Are you sure you want to exit?"
        reply = QMessageBox.question(self, 'Really exit?',  quit_msg,
                                     QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            event.ignore()
            return
        # If subthreads aren't shut down, we get a segfault when we quit.
        # However, right now, signals aren't being processed because we're in
        # the GUI message loop. So we need to defer the call if subthreads are
        # running
        if not self.anything_running():
            event.accept()
            return
        # Now stop everything
        log.warn("Waiting for threads to finish...")
        self.exit_pending = True
        if self.whisker_owner:
            self.whisker_owner.stop()
        # Will get a callback to task_finished
        event.ignore()

    # *** require further check to exit if task is actually running

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    @Slot()
    def configure(self):
        readonly = self.anything_running()
        with session_thread_scope(self.dbsettings, readonly) as session:
            w = ConfigPicker(session)
            self.config_id = w.exec_returning_config_id()
        self.report_selected_config()
        self.set_button_states()

    def report_selected_config(self):
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

    @exit_on_exception
    @Slot()
    def start(self):
        if self.anything_running():
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
                self.config_id = frozen_config.id
                self.whisker_task = SerialOrderTask(self.dbsettings,
                                                    frozen_config.id)
                self.whisker_owner = WhiskerOwner(
                    self.whisker_task, frozen_config.server,
                    main_port=frozen_config.port, parent=self)
        except AttributeError as e:
            traceback.print_exc()
            log.debug("start: error: {}".format(e))
            QMessageBox.about(self, "Can't start",
                              "Failed to start; config not set.")
            return
        self.report_selected_config()
        self.whisker_task.task_status_sig.connect(self.report)
        self.whisker_owner.finished.connect(self.task_finished)
        self.whisker_owner.start()
        self.set_button_states()

    @Slot()
    def stop(self):
        if not self.anything_running():
            QMessageBox.about(self, "Can't stop",
                              "Nothing to stop: not running.")
            return
        self.status("Stopping...")
        if self.whisker_owner:
            self.whisker_owner.stop()
        self.set_button_states()

    @Slot()
    def task_finished(self):
        self.status("Task finished")
        self.whisker_owner = None
        if self.exit_pending:
            QApplication.quit()
        self.report("Finished.")
        self.set_button_states()

    def anything_running(self):
        """Returns a bool."""
        return (self.whisker_owner is not None
                and self.whisker_owner.is_running())

    def set_button_states(self):
        running = self.anything_running()
        self.configure_button.setText(
            'View configuration'
            if running and not self.db_is_sqlite else '&Configure')
        self.configure_button.setEnabled(not running or not self.db_is_sqlite)
        self.start_button.setEnabled(not running
                                     and self.config_id is not None)
        self.stop_button.setEnabled(running)
        self.ping_whisker_button.setEnabled(running)

    # -------------------------------------------------------------------------
    # Status log
    # -------------------------------------------------------------------------

    @Slot(str, str)
    def on_status(self, msg, source=""):
        # http://stackoverflow.com/questions/16568451
        if source:
            msg = "[{}] {}".format(source, msg)
        if self.log.toPlainText():
            msg = "\n" + msg
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(msg)
        self.scroll_to_end_of_log()

    def status(self, msg):
        self.on_status(msg, "main")

    def copy_whole_log(self):
        # Ctrl-C will copy the selected parts.
        # log.copy() will copy the selected parts.
        self.log.selectAll()
        self.log.copy()
        self.log.moveCursor(QTextCursor.End)
        self.scroll_to_end_of_log()

    def scroll_to_end_of_log(self):
        vsb = self.log.verticalScrollBar()
        vsb.setValue(vsb.maximum())
        hsb = self.log.horizontalScrollBar()
        hsb.setValue(0)

    # -------------------------------------------------------------------------
    # Status summary
    # -------------------------------------------------------------------------

    def report(self, msg):
        self.status_msg.setText(msg)

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------

    @Slot()
    def ping_whisker(self):
        if self.whisker_owner:
            self.whisker_owner.ping()

    @Slot()
    def about(self):
        QMessageBox.about(self, WINDOW_TITLE, ABOUT)

    @Slot()
    def help(self):
        # launch_external_file(MANUAL_FILENAME)
        # self.status("Launched {}".format(MANUAL_FILENAME))
        QMessageBox.about(self, WINDOW_TITLE, "*** to do ***")


# =============================================================================
# Choose a config
# =============================================================================

class ConfigAttrTableModel(GenericAttrTableModel):
    CONFIG_HEADINGS = [
        ("ID", "id"),
        ("Modified", "get_modified_at_pretty",),
        ("Subject", "subject"),
        ("Server", "server"),
        ("Port", "port"),
        ("Box", "devicegroup"),
    ]
    DEFAULT_SORT_COLUMN_NAME = "get_modified_at_pretty"

    def __init__(self, listdata, session, **kwargs):
        super().__init__(
            listdata, self.CONFIG_HEADINGS, session,
            default_sort_column_name=self.DEFAULT_SORT_COLUMN_NAME,
            default_sort_order=Qt.DescendingOrder,
            **kwargs
        )


class ConfigPicker(TransactionalDialog):
    """
    Chooses a Config object.
    """
    def __init__(self, session, parent=None, readonly=False):
        super().__init__(session=session, readonly=readonly, parent=parent)
        self.session = session
        self.readonly = readonly

        self.setWindowTitle("Choose configuration for Serial Order Task")

        instruction_1 = QLabel(
            "Select a config from the Editable list, then click OK.")

        editable_group = StyledQGroupBox('Editable configurations')
        editable_layout = QHBoxLayout()
        editable_button_layout = QVBoxLayout()
        self.ed_tv = GenericAttrTableView(self.session, ConfigWindow,
                                          readonly=self.readonly)
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
        self.ro_tv = GenericAttrTableView(self.session, ConfigWindow,
                                          readonly=True)  # always readonly
        readonly_layout.addWidget(self.ro_tv)
        self.ro_view_button = QPushButton("View")
        readonly_button_layout.addWidget(self.ro_view_button)
        if not readonly:
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

    def exec_(self):
        # http://stackoverflow.com/questions/18998010/flake8-complains-on-boolean-comparison-in-filter-clause  # noqa
        ro_configs = self.session.query(Config).filter(
            Config.read_only == False).all()  # noqa
        ed_configs = self.session.query(Config).filter(
            Config.read_only == True).all()  # noqa
        ro_model = ConfigAttrTableModel(ro_configs, self.session)
        ed_model = ConfigAttrTableModel(ed_configs, self.session,
                                        deletable=False)
        self.ed_tv.setModel(ro_model)
        self.ro_tv.setModel(ed_model)
        return super().exec_()

    def exec_returning_config_id(self):
        result = self.exec_()
        if result != QDialog.Accepted:
            return None
        obj = self.ed_tv.get_selected_object()
        if obj is None:
            return
        return obj.id

    def set_ed_button_states(self):
        selected = self.ed_tv.is_selected()
        self.ed_edit_button.setEnabled(selected)
        self.ed_add_button.setEnabled(not self.readonly)
        self.ed_clone_button.setEnabled(selected and not self.readonly)
        self.ed_delete_button.setEnabled(selected and not self.readonly)
        self.ok_button.setEnabled(selected)

    def set_ro_button_states(self):
        selected = self.ro_tv.is_selected()
        self.ro_view_button.setEnabled(selected)
        self.ro_clone_button.setEnabled(selected)

    def delete_ed(self):
        self.ed_tv.remove_selected()

    def add_ed(self):
        # TO ADD IMMEDIATELY WITHOUT VALIDATION:
        # self.ed_tv.insert_at_start(Config(), add_to_session=True)
        # TO ADD/VALIDATE TRANSACTIONALLY:
        self.ed_tv.add_in_nested_transaction(Config())

    def edit_view_ed(self):
        self.ed_tv.edit_selected()

    def view_ro(self):
        self.ro_tv.edit_selected()

    def clone_ed(self):
        obj = self.ed_tv.get_selected_object()
        if obj is None:
            return
        newobj = obj.clone(self.session, read_only=False)
        self.ed_tv.insert_at_start(newobj, add_to_session=True)
        # ... OK to add something to a session twice

    def clone_ro(self):
        obj = self.ro_tv.get_selected_object()
        if obj is None:
            return
        newobj = obj.clone(self.session, read_only=False)
        # Ensure it is NOT read-only, and add it to the EDITABLE list.
        self.ed_tv.insert_at_start(newobj, add_to_session=True)


# =============================================================================
# Edit main config
# =============================================================================

class ConfigWindow(QDialog, TransactionalEditDialogMixin):
    """
    Edits a Config object.
    """
    def __init__(self, session, config, parent=None, readonly=False):
        super().__init__(parent)  # QDialog

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

        iti_group = StyledQGroupBox('Intertrial interval (ITI)')
        iti_form = QFormLayout()
        iti_form.addRow("ITI duration (ms)", self.iti_edit)
        iti_group.setLayout(iti_form)



        main_layout = QVBoxLayout()
        main_layout.addWidget(whisker_group)
        main_layout.addWidget(subject_group)
        main_layout.addWidget(reinf_group)
        main_layout.addWidget(iti_group)

        # Shared code
        TransactionalEditDialogMixin.__init__(self, session, config,
                                              main_layout, readonly=readonly)

    def object_to_dialog(self, obj):
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

    def dialog_to_object(self, obj):
        # Master config validation and cross-checks.
        # ---------------------------------------------------------------------
        # Basic checks
        # ---------------------------------------------------------------------
        try:
            obj.server = self.server_edit.text()
            assert len(obj.server) > 0
        except:
            raise ValidationError("Invalid server name")
        try:
            obj.port = int(self.port_edit.text())
            assert obj.port > 0
        except:
            raise ValidationError("Invalid port number")
        try:
            obj.devicegroup = self.devicegroup_edit.text()
            assert len(obj.devicegroup) > 0
        except:
            raise ValidationError("Invalid device group name")

        try:
            obj.subject = self.subject_edit.text()
            assert len(obj.subject) > 0
        except:
            raise ValidationError("Invalid subject name")

        try:
            obj.reinf_n_pellets = int(self.reinf_n_pellets_edit.text())
            assert obj.reinf_n_pellets > 0
        except:
            raise ValidationError("Invalid # pellets")
        try:
            obj.reinf_pellet_pulse_ms = int(
                self.reinf_pellet_pulse_ms_edit.text())
            assert obj.reinf_pellet_pulse_ms > 0
        except:
            raise ValidationError("Invalid pellet pulse time")
        try:
            obj.reinf_interpellet_gap_ms = int(
                self.reinf_interpellet_gap_ms_edit.text())
            assert obj.reinf_interpellet_gap_ms > 0
        except:
            raise ValidationError("Invalid interpellet gap")

        try:
            obj.iti_duration_ms = int(self.iti_edit.text())
            assert obj.iti_duration_ms > 0
        except:
            raise ValidationError("Invalid ITI duration")
