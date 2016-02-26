#!/usr/bin/env python
# whisker_serial_order/gui.py

import collections
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import platform

from PySide.QtCore import Qt, Slot
from PySide.QtGui import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
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
from sqlalchemy.sql import exists


# =============================================================================
# Secondary GUI windows
# =============================================================================

class NoDatabaseSpecifiedWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        info = QLabel(DATABASE_ENV_VAR_NOT_SPECIFIED)
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
        layout_upgrade.addStretch(1)
        main_layout = QVBoxLayout()
        main_layout.addWidget(info)
        main_layout.addLayout(layout_upgrade)
        main_layout.addWidget(ok_buttons)
        self.setLayout(main_layout)

    @Slot()
    def upgrade_database(self):
        try:
            upgrade_database()
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
    NAME = "main"
