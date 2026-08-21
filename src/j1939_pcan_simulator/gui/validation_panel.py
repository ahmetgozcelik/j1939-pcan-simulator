"""Dockable validation issue list for workspace diagnostics."""

from __future__ import annotations

from typing import Iterable

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from j1939_pcan_simulator.config.workspace import Workspace
from j1939_pcan_simulator.validation.workspace import ValidationIssue


COL_SEVERITY = 0
COL_LOCATION = 1
COL_FIELD = 2
COL_CODE = 3
COL_MESSAGE = 4
COLS = ["Severity", "Location", "Field", "Code", "Message"]


class ValidationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.summary = QLabel("Validation OK")
        self.summary.setObjectName("ValidationSummary")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, len(COLS))
        self.table.setObjectName("ValidationTable")
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(COL_SEVERITY, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_LOCATION, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_FIELD, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_CODE, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_MESSAGE, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def set_issues(self, workspace: Workspace, issues: Iterable[ValidationIssue]) -> None:
        issue_list = list(issues)
        errors = sum(1 for issue in issue_list if issue.severity == "error")
        warnings = sum(1 for issue in issue_list if issue.severity == "warning")
        if errors or warnings:
            self.summary.setText(f"{errors} error(s), {warnings} warning(s)")
            self.summary.setProperty("state", "error" if errors else "warn")
        else:
            self.summary.setText("Validation OK")
            self.summary.setProperty("state", "ok")
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)

        self.table.setRowCount(len(issue_list))
        self.table.setVisible(bool(issue_list))
        for row, issue in enumerate(issue_list):
            values = [
                issue.severity.upper(),
                self._location_text(workspace, issue),
                issue.field or "-",
                issue.code,
                issue.message,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.UserRole, issue)
                if col in (COL_FIELD, COL_CODE):
                    font = QFont("JetBrains Mono")
                    font.setStyleHint(QFont.Monospace)
                    item.setFont(font)
                if col == COL_SEVERITY:
                    item.setData(Qt.UserRole + 1, issue.severity)
                self.table.setItem(row, col, item)

    def _location_text(self, workspace: Workspace, issue: ValidationIssue) -> str:
        if issue.message_index is None:
            return "Workspace"
        msg_number = issue.message_index + 1
        if not (0 <= issue.message_index < len(workspace.messages)):
            return f"Message {msg_number}"
        message = workspace.messages[issue.message_index]
        base = f"Message {msg_number}: {message.can_id}"
        if message.name:
            base += f" - {message.name}"
        if issue.signal_index is None:
            return base
        sig_number = issue.signal_index + 1
        if not (0 <= issue.signal_index < len(message.signals)):
            return f"{base} / Signal {sig_number}"
        signal = message.signals[issue.signal_index]
        return f"{base} / Signal {sig_number}: {signal.name}"

