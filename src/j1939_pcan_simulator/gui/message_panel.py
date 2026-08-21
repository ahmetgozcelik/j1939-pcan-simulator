"""Left panel containing the CAN message list.

This panel owns the message table, message CRUD buttons, start/stop controls,
and CAN connection controls.
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
from PyQt5.QtGui import QColor, QFont
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

from j1939_pcan_simulator.config.workspace import Message, Workspace, clone_message
from j1939_pcan_simulator.gui.table_delegates import MessageTableDelegate, ROLE_ACTIVE_STATE, ROLE_TYPE_KIND
from j1939_pcan_simulator.gui.theme import repolish, theme_color
from j1939_pcan_simulator.protocol.identifier import PGN_DM1, PGN_DM2, PgnCategory, build_can_id, format_can_id, parse_can_id


# ---------------------------------------------------------------------------
# Small helper that wraps UI command handlers with error reporting.
# ---------------------------------------------------------------------------


def _safe_slot(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            tb = traceback.format_exc()
            try:
                from j1939_pcan_simulator.app.error_reporter import report

                report(f"{fn.__qualname__}:\n{tb}")
            except Exception:
                sys.__stderr__.write(tb)

    return wrapper


COL_ACTIVE = 0
COL_ID = 1
COL_PGN = 2
COL_PGN_DEC = 3
COL_PRIORITY = 4
COL_SA = 5
COL_DA_GE = 6
COL_TYPE = 7
COL_NAME = 8
COL_CYCLE = 9
COLS = ["Active", "CAN ID", "PGN Hex", "PGN Dec", "Prio", "SA", "DA/GE", "Type", "Name", "Cycle ms"]
DEFAULT_NEW_MESSAGE_PGN = 0x00FF00
MONOSPACE_COLS = {COL_ID, COL_PGN, COL_PGN_DEC, COL_SA, COL_DA_GE}


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
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            if section == COL_TYPE:
                return "Derived from the J1939 PGN/CAN ID. Edit PGN Hex, PGN Dec, or CAN ID to change it."
            if section in (COL_ID, COL_PGN, COL_PGN_DEC, COL_PRIORITY, COL_SA, COL_DA_GE):
                return "Editable J1939 identifier field"
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        col = index.column()
        if col == COL_ACTIVE:
            return base
        if col in (
            COL_ID,
            COL_PGN,
            COL_PGN_DEC,
            COL_PRIORITY,
            COL_SA,
            COL_DA_GE,
            COL_NAME,
            COL_CYCLE,
        ):
            return base | Qt.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        msg = self.messages()[index.row()]
        col = index.column()
        parsed = _parse_message_id(msg)
        if role == ROLE_ACTIVE_STATE and col == COL_ACTIVE:
            return msg.active
        if role == ROLE_TYPE_KIND and col == COL_TYPE:
            return _category_label(parsed.category) if parsed else "invalid"
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == COL_ACTIVE:
                return ""
            if col == COL_ID:
                return msg.can_id
            if col == COL_PGN:
                return f"{parsed.pgn:05X}" if parsed else ""
            if col == COL_PGN_DEC:
                return parsed.pgn if parsed else ""
            if col == COL_PRIORITY:
                return parsed.priority if parsed else ""
            if col == COL_SA:
                return f"{parsed.source_address:02X}" if parsed else ""
            if col == COL_DA_GE:
                if not parsed:
                    return ""
                if parsed.destination_address is not None:
                    return f"DA {parsed.destination_address:02X}"
                return f"GE {parsed.group_extension:02X}"
            if col == COL_TYPE:
                return _category_label(parsed.category) if parsed else "invalid"
            if col == COL_NAME:
                return msg.name
            if col == COL_CYCLE:
                return int(msg.cycle_ms)
        if role == Qt.ForegroundRole:
            if parsed is None:
                return theme_color("status-error")
            if col in (COL_ID, COL_PGN, COL_PGN_DEC, COL_TYPE):
                return _category_color(parsed.category)
        if role == Qt.FontRole and col in MONOSPACE_COLS:
            font = QFont("JetBrains Mono")
            font.setStyleHint(QFont.Monospace)
            return font
        if role == Qt.TextAlignmentRole and col in (
            COL_ACTIVE,
            COL_ID,
            COL_PGN,
            COL_PGN_DEC,
            COL_PRIORITY,
            COL_SA,
            COL_DA_GE,
            COL_TYPE,
            COL_CYCLE,
        ):
            return int(Qt.AlignCenter)
        if role == Qt.ToolTipRole:
            if parsed is None:
                return "Invalid 29-bit J1939 CAN ID"
            if col == COL_ACTIVE:
                return "Click to toggle message transmission state"
            if col in (COL_ID, COL_PGN, COL_PGN_DEC, COL_PRIORITY, COL_SA, COL_DA_GE):
                return "Double-click to edit J1939 identifier fields"
            if col == COL_TYPE:
                return f"{_category_tooltip(parsed.category)}. Edit PGN Hex, PGN Dec, or CAN ID to change Type."
            if col == COL_DA_GE:
                return "Destination address" if parsed.is_pdu1 else "Group extension"
            if col == COL_NAME:
                return msg.name
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
                elif col == COL_PGN:
                    msg.can_id = _updated_can_id(msg, pgn=_parse_pgn_value(value, default_base=16))
                elif col == COL_PGN_DEC:
                    msg.can_id = _updated_can_id(msg, pgn=_parse_pgn_value(value, default_base=10))
                elif col == COL_PRIORITY:
                    msg.can_id = _updated_can_id(msg, priority=_parse_number(value, 0, 7, base=10))
                elif col == COL_SA:
                    msg.can_id = _updated_can_id(msg, source_address=_parse_number(value, 0, 0xFF, base=16))
                elif col == COL_DA_GE:
                    msg.can_id = _updated_can_id(msg, pdu_specific=_parse_da_ge_value(value))
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
            _apply_protocol_default_name(msg)
            left = self.index(index.row(), 0)
            right = self.index(index.row(), len(COLS) - 1)
            self.dataChanged.emit(left, right, [Qt.DisplayRole])
            return True
        return False

    def set_active(self, row: int, active: bool) -> Optional[Message]:
        msgs = self.messages()
        if not (0 <= row < len(msgs)):
            return None
        msg = msgs[row]
        if msg.active == active:
            return msg
        msg.active = active
        index = self.index(row, COL_ACTIVE)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, ROLE_ACTIVE_STATE])
        return msg


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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # PCAN status row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status_badge = QWidget()
        self.status_badge.setObjectName("ConnectionBadge")
        badge_layout = QHBoxLayout(self.status_badge)
        badge_layout.setContentsMargins(10, 5, 10, 5)
        badge_layout.setSpacing(7)
        self.led = QLabel()
        self.led.setObjectName("ConnectionLed")
        self.led.setFixedSize(12, 12)
        self._set_led(False)
        self.lbl_status = QLabel("CAN: DISCONNECTED")
        self.lbl_status.setObjectName("ConnectionStatusLabel")
        badge_layout.addWidget(self.led)
        badge_layout.addWidget(self.lbl_status)

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
        self.btn_reconnect.setObjectName("ReconnectButton")
        self.btn_reconnect.clicked.connect(self.request_reconnect.emit)
        
        status_row.addWidget(self.status_badge)
        status_row.addWidget(self.combo_backend)
        status_row.addWidget(self.combo_channel)
        status_row.addWidget(self.combo_bitrate)
        status_row.addWidget(self.btn_reconnect)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        # Table
        self.model = MessageTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMouseTracking(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setItemDelegate(MessageTableDelegate(COL_ACTIVE, COL_TYPE, self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hh = self.table.horizontalHeader()
        hh.setSectionsMovable(True)
        hh.setSectionsClickable(True)
        hh.setMinimumSectionSize(44)
        for col, width in {
            COL_ACTIVE: 64,
            COL_ID: 112,
            COL_PGN: 88,
            COL_PGN_DEC: 88,
            COL_PRIORITY: 56,
            COL_SA: 54,
            COL_DA_GE: 82,
            COL_TYPE: 112,
            COL_NAME: 240,
            COL_CYCLE: 92,
        }.items():
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)
        hh.setStretchLastSection(False)
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
        self.btn_start_all = QPushButton("Start Active")
        self.btn_stop_all = QPushButton("Stop All")
        self.btn_start_all.clicked.connect(self.request_start_all.emit)
        self.btn_stop_all.clicked.connect(self.request_stop_all.emit)
        row2.addWidget(self.btn_start_all)
        row2.addWidget(self.btn_stop_all)
        layout.addLayout(row2)

        # Selection / data change wiring
        self.table.selectionModel().selectionChanged.connect(self._emit_selection)
        self.table.clicked.connect(self._on_table_clicked)
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
            text = "CAN: CONNECTED"
            tooltip = f"Connected: {info}" if info else "Connected"
        else:
            text = "CAN: DISCONNECTED"
            tooltip = f"Disconnected: {info}" if info else "Disconnected"
        self.lbl_status.setText(text)
        self.lbl_status.setToolTip(tooltip)
        self.status_badge.setToolTip(tooltip)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_led(self, on: bool) -> None:
        state = "ok" if on else "error"
        self.led.setProperty("state", state)
        self.status_badge.setProperty("state", state)
        repolish(self.led)
        repolish(self.status_badge)

    @_safe_slot
    def _emit_selection(self, *_args) -> None:
        self.message_selected.emit(self.selected_message())

    @_safe_slot
    def _on_data_changed(self, top_left, bottom_right, roles=None) -> None:
        self.workspace_modified.emit()
        # Notify the engine when the active indicator changes.
        if roles and Qt.CheckStateRole in roles:
            row = top_left.row()
            msgs = self.model.messages()
            if 0 <= row < len(msgs):
                self.request_active_changed.emit(msgs[row])

    @_safe_slot
    def _on_table_clicked(self, index: QModelIndex) -> None:
        if not index.isValid() or index.column() != COL_ACTIVE:
            return
        msg = self.model.set_active(index.row(), not bool(index.data(ROLE_ACTIVE_STATE)))
        if msg is not None:
            self.request_active_changed.emit(msg)

    @_safe_slot
    def _add_message(self, checked = False) -> None:
        msgs = self.model.messages()
        msg = Message(
            can_id=_suggest_unique_can_id(
                build_can_id(priority=6, pgn=DEFAULT_NEW_MESSAGE_PGN, source_address=0),
                _used_can_ids(msgs),
            ),
            name="New J1939 Message",
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
        copy.can_id = _suggest_unique_can_id(copy.can_id, _used_can_ids(msgs))
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
            msg = msgs[idx]
            if msg.active:
                msg.active = False
                self.request_active_changed.emit(msg)
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


def _used_can_ids(messages: List[Message]) -> set[str]:
    used: set[str] = set()
    for msg in messages:
        try:
            used.add(format_can_id(msg.can_id))
        except ValueError:
            continue
    return used


def _suggest_unique_can_id(base_can_id: int | str, used_ids: set[str]) -> str:
    try:
        parsed = parse_can_id(base_can_id)
    except ValueError:
        parsed = parse_can_id("18FF0000")

    if parsed.to_hex() not in used_ids:
        return parsed.to_hex()

    for offset in range(1, 254):
        source_address = (parsed.source_address + offset) % 254
        candidate = build_can_id(
            priority=parsed.priority,
            pgn=parsed.pgn,
            source_address=source_address,
            destination_address=parsed.destination_address,
            group_extension=parsed.group_extension,
        )
        candidate_hex = format_can_id(candidate)
        if candidate_hex not in used_ids:
            return candidate_hex

    return parsed.to_hex()


def _parse_message_id(msg: Message):
    try:
        return parse_can_id(msg.can_id)
    except ValueError:
        return None


def _parse_number(value, low: int, high: int, *, base: int | None = None) -> int:
    text = str(value).strip().upper()
    text = text.replace("0X", "").replace("PGN", "").replace("SA", "")
    text = text.replace("PRIO", "").replace("PRIORITY", "").strip()
    if not text:
        raise ValueError("empty numeric value")
    number_base = base or (16 if any(ch in "ABCDEF" for ch in text) else 10)
    number = int(text, number_base)
    if not low <= number <= high:
        raise ValueError(f"value must be in {low}..{high}")
    return number


def _parse_pgn_value(value, *, default_base: int) -> int:
    text = str(value).strip().upper()
    text = text.replace("PGN", "").replace(":", "").strip()
    if not text:
        raise ValueError("empty PGN")
    if text.startswith("0X"):
        number = int(text[2:], 16)
    elif any(ch in "ABCDEF" for ch in text):
        number = int(text, 16)
    else:
        number = int(text, default_base)
    if not 0 <= number <= 0x3FFFF:
        raise ValueError("PGN must be in 0..262143")
    return number


def _parse_da_ge_value(value) -> int:
    text = str(value).strip().upper()
    text = text.replace("DA", "").replace("GE", "").replace(":", "").strip()
    return _parse_number(text, 0, 0xFF, base=16)


def _updated_can_id(
    msg: Message,
    *,
    pgn: Optional[int] = None,
    priority: Optional[int] = None,
    source_address: Optional[int] = None,
    pdu_specific: Optional[int] = None,
) -> str:
    parsed = parse_can_id(msg.can_id)
    new_priority = parsed.priority if priority is None else priority
    new_pgn = parsed.pgn if pgn is None else pgn
    new_source = parsed.source_address if source_address is None else source_address

    pf = (new_pgn >> 8) & 0xFF
    if pf < 0xF0:
        if new_pgn & 0xFF:
            raise ValueError("PDU1 PGNs must end with 00")
        destination = (
            parsed.destination_address
            if pdu_specific is None
            else pdu_specific
        )
        if destination is None:
            destination = 0xFF
        can_id = build_can_id(
            priority=new_priority,
            pgn=new_pgn,
            source_address=new_source,
            destination_address=destination,
        )
    else:
        group_extension = pdu_specific
        if group_extension is not None:
            new_pgn = (new_pgn & 0x3FF00) | group_extension
        can_id = build_can_id(
            priority=new_priority,
            pgn=new_pgn,
            source_address=new_source,
            group_extension=group_extension,
        )
    return format_can_id(can_id)


def _category_label(category: PgnCategory) -> str:
    return {
        PgnCategory.STANDARD: "standard",
        PgnCategory.REQUEST: "request",
        PgnCategory.TRANSPORT: "transport",
        PgnCategory.DIAGNOSTIC: "diagnostic",
        PgnCategory.PROPRIETARY_A: "prop A",
        PgnCategory.PROPRIETARY_B: "prop B",
        PgnCategory.UNKNOWN: "unknown",
    }[category]


def _apply_protocol_default_name(msg: Message) -> None:
    if msg.name not in {"", "Message", "New J1939 Message"}:
        return
    try:
        parsed = parse_can_id(msg.can_id)
    except ValueError:
        return
    if parsed.pgn == PGN_DM1:
        msg.name = "DM1 - Active Diagnostic Trouble Codes"
    elif parsed.pgn == PGN_DM2:
        msg.name = "DM2 - Previously Active Diagnostic Trouble Codes"


def _category_tooltip(category: PgnCategory) -> str:
    return {
        PgnCategory.STANDARD: "Standard SAE J1939 PGN",
        PgnCategory.REQUEST: "J1939 request PGN",
        PgnCategory.TRANSPORT: "J1939 transport protocol PGN",
        PgnCategory.DIAGNOSTIC: "J1939 diagnostic PGN",
        PgnCategory.PROPRIETARY_A: "J1939 proprietary A PGN",
        PgnCategory.PROPRIETARY_B: "J1939 proprietary B PGN",
        PgnCategory.UNKNOWN: "Unknown PGN category",
    }[category]


def _category_color(category: PgnCategory) -> QColor:
    return {
        PgnCategory.STANDARD: theme_color("text-primary"),
        PgnCategory.REQUEST: theme_color("accent-cyan"),
        PgnCategory.TRANSPORT: theme_color("status-ok"),
        PgnCategory.DIAGNOSTIC: theme_color("status-warn"),
        PgnCategory.PROPRIETARY_A: theme_color("text-secondary"),
        PgnCategory.PROPRIETARY_B: theme_color("text-secondary"),
        PgnCategory.UNKNOWN: theme_color("status-error"),
    }[category]

