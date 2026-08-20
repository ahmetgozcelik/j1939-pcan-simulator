"""Sol panel: tüm CAN mesajlarının listesi.

Aktif checkbox, CAN ID, isim, cycle (ms) sütunları. Add / Delete / Duplicate
butonları ve Start All / Stop All butonları. PCAN bağlantı LED'i de buradadır.
"""

from __future__ import annotations

import functools
import sys
import traceback
from typing import List, Optional

from PyQt5.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from config_manager import Message, Workspace, clone_message


# ---------------------------------------------------------------------------
# Buton handler'larını try/except ile saran küçük yardımcı.
# ---------------------------------------------------------------------------


def _safe_slot(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            tb = traceback.format_exc()
            try:
                from error_reporter import report

                report(f"{fn.__qualname__}:\n{tb}")
            except Exception:
                sys.__stderr__.write(tb)

    return wrapper


COL_ACTIVE = 0
COL_ID = 1
COL_NAME = 2
COL_CYCLE = 3
COLS = ["Active", "CAN ID", "Name", "Cycle ms"]


class MessageTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workspace: Optional[Workspace] = None

    def set_workspace(self, ws: Workspace) -> None:
        self.beginResetModel()
        self._workspace = ws
        self.endResetModel()

    def messages(self) -> List[Message]:
        return self._workspace.messages if self._workspace else []

    # -------- overrides --------

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.messages())

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLS[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        col = index.column()
        if col == COL_ACTIVE:
            return base | Qt.ItemIsUserCheckable
        if col in (COL_ID, COL_NAME, COL_CYCLE):
            return base | Qt.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        msg = self.messages()[index.row()]
        col = index.column()
        if role == Qt.CheckStateRole and col == COL_ACTIVE:
            return Qt.Checked if msg.active else Qt.Unchecked
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == COL_ID:
                return msg.can_id
            if col == COL_NAME:
                return msg.name
            if col == COL_CYCLE:
                return int(msg.cycle_ms)
        if role == Qt.ForegroundRole and col == COL_ID and msg.is_dm1():
            return QColor(255, 200, 100)
        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        msg = self.messages()[index.row()]
        col = index.column()
        if role == Qt.CheckStateRole and col == COL_ACTIVE:
            msg.active = value == Qt.Checked
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        if role == Qt.EditRole:
            try:
                if col == COL_ID:
                    cleaned = str(value).strip().upper().replace("0X", "").replace(" ", "")
                    int(cleaned, 16)  # validate
                    msg.can_id = cleaned
                elif col == COL_NAME:
                    msg.name = str(value)
                elif col == COL_CYCLE:
                    cm = int(value)
                    if cm < 1:
                        return False
                    msg.cycle_ms = cm
                else:
                    return False
            except ValueError:
                return False
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            return True
        return False


class MessagePanel(QWidget):

    message_selected = pyqtSignal(object)  # Message or None
    workspace_modified = pyqtSignal()
    request_start_all = pyqtSignal()
    request_stop_all = pyqtSignal()
    request_active_changed = pyqtSignal(object)  # Message
    request_reconnect = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # PCAN status row
        '''
        status_row = QHBoxLayout()
        self.led = QLabel()
        self.led.setObjectName("statusLed")
        self.led.setFixedSize(14, 14)
        self._set_led(False)
        self.lbl_status = QLabel("PCAN: disconnected")
        self.btn_reconnect = QPushButton("Reconnect")
        self.btn_reconnect.clicked.connect(self.request_reconnect.emit)
        status_row.addWidget(self.led)
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.btn_reconnect)
        layout.addLayout(status_row)
        '''

        # PCAN status row
        status_row = QHBoxLayout()
        self.led = QLabel()
        self.led.setObjectName("statusLed")
        self.led.setFixedSize(14, 14)
        self._set_led(False)
        self.lbl_status = QLabel("PCAN: disconnected")

        # ComboBox'lar
        self.combo_backend = QComboBox()
        self.combo_backend.addItem("PCAN", "pcan")
        self.combo_backend.addItem("Virtual", "virtual")

        self.combo_channel = QComboBox()
        for i in range(1, 9):
            self.combo_channel.addItem(f'PCAN_USBBUS{i}')
        self.combo_channel.addItem("j1939-simulator")
            
        self.combo_bitrate = QComboBox()
        self.combo_bitrate.addItems(['125 kbps', '250 kbps', '500 kbps', '1 Mbps'])
        self.combo_bitrate.setCurrentIndex(1)  # 250 kbps default

        self.btn_reconnect = QPushButton("Reconnect")
        self.btn_reconnect.clicked.connect(self.request_reconnect.emit)
        
        status_row.addWidget(self.led)
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.combo_backend)
        status_row.addWidget(self.combo_channel)
        status_row.addWidget(self.combo_bitrate)
        status_row.addWidget(self.btn_reconnect)
        layout.addLayout(status_row)

        # Table
        self.model = MessageTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_ACTIVE, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_ID, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_CYCLE, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        layout.addWidget(self.table, 1)

        # Buttons row 1
        row1 = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_dup = QPushButton("Duplicate")
        self.btn_del = QPushButton("Delete")
        self.btn_add.clicked.connect(self._add_message)
        self.btn_dup.clicked.connect(self._duplicate_message)
        self.btn_del.clicked.connect(self._delete_message)
        row1.addWidget(self.btn_add)
        row1.addWidget(self.btn_dup)
        row1.addWidget(self.btn_del)
        layout.addLayout(row1)

        # Buttons row 2
        row2 = QHBoxLayout()
        self.btn_start_all = QPushButton("Start All")
        self.btn_stop_all = QPushButton("Stop All")
        self.btn_start_all.clicked.connect(self.request_start_all.emit)
        self.btn_stop_all.clicked.connect(self.request_stop_all.emit)
        row2.addWidget(self.btn_start_all)
        row2.addWidget(self.btn_stop_all)
        layout.addLayout(row2)

        # Selection / data change wiring
        self.table.selectionModel().selectionChanged.connect(self._emit_selection)
        self.model.dataChanged.connect(self._on_data_changed)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_workspace(self, ws: Workspace) -> None:
        self.model.set_workspace(ws)
        if ws.messages:
            self.table.selectRow(0)
        else:
            self.message_selected.emit(None)

    def selected_message(self) -> Optional[Message]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        msgs = self.model.messages()
        return msgs[idx] if 0 <= idx < len(msgs) else None

    def update_connection_status(self, connected: bool, info: str) -> None:
        self._set_led(connected)
        if connected:
            text = f"PCAN: connected ({info})"
        else:
            text = "PCAN: disconnected"
            if info:
                text += f" - {info}"
        self.lbl_status.setText(text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_led(self, on: bool) -> None:
        color = "#2ecc71" if on else "#e74c3c"
        self.led.setStyleSheet(
            f"background-color: {color}; border-radius: 7px;"
        )

    @_safe_slot
    def _emit_selection(self, *_args) -> None:
        self.message_selected.emit(self.selected_message())

    @_safe_slot
    def _on_data_changed(self, top_left, bottom_right, roles=None) -> None:
        self.workspace_modified.emit()
        # Aktif checkbox değiştiyse motorun haberi olsun.
        if roles and Qt.CheckStateRole in roles:
            row = top_left.row()
            msgs = self.model.messages()
            if 0 <= row < len(msgs):
                self.request_active_changed.emit(msgs[row])

    @_safe_slot
    def _add_message(self, checked = False) -> None:
        msgs = self.model.messages()
        msg = Message(
            can_id="18FFFFFF",
            name="New Message",
            cycle_ms=1000,
            active=False,
            signals=[],
        )
        self.model.beginResetModel()
        msgs.append(msg)
        self.model.endResetModel()
        self.workspace_modified.emit()
        self.table.selectRow(len(msgs) - 1)

    @_safe_slot
    def _duplicate_message(self, checked = False) -> None:
        msg = self.selected_message()
        if msg is None:
            return
        copy = clone_message(msg)
        copy.name = msg.name + " (copy)"
        copy.active = False
        msgs = self.model.messages()
        self.model.beginResetModel()
        msgs.append(copy)
        self.model.endResetModel()
        self.workspace_modified.emit()
        self.table.selectRow(len(msgs) - 1)

    @_safe_slot
    def _delete_message(self, checked = False) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        msgs = self.model.messages()
        if 0 <= idx < len(msgs):
            self.model.beginResetModel()
            del msgs[idx]
            self.model.endResetModel()
            self.workspace_modified.emit()
            if msgs:
                self.table.selectRow(min(idx, len(msgs) - 1))
            else:
                self.message_selected.emit(None)

    def refresh_row_for_message(self, msg: Message) -> None:
        msgs = self.model.messages()
        try:
            row = msgs.index(msg)
        except ValueError:
            return
        left = self.model.index(row, 0)
        right = self.model.index(row, len(COLS) - 1)
        self.model.dataChanged.emit(left, right, [Qt.DisplayRole])
