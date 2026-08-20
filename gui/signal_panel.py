"""Orta panel: seçili mesajın sinyal tablosu.

Inline raw/physical edit destekler. Mesaj DM1 ise bu panelin yerine üst pencere
``DM1Panel`` gösterir; bu modül yalnızca normal mesajlar için kullanılır.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from config_manager import Message, Signal
from frame_builder import physical_to_raw, raw_to_physical
from gui.table_delegates import HmiTableDelegate
from gui.theme import theme_color
from validators import signal_bit_positions


COL_NAME = 0
COL_RAW = 1
COL_PHYS = 2
COL_UNIT = 3
COL_MODE = 4
COLS = ["Signal Name", "Raw Value", "Physical Value", "Unit", "Mode"]


class SignalTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._message: Optional[Message] = None
        self._flashed_rows: set[int] = set()

    def set_message(self, msg: Optional[Message]) -> None:
        self.beginResetModel()
        self._message = msg
        self.endResetModel()

    def message(self) -> Optional[Message]:
        return self._message

    # ----- required overrides --------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid() or self._message is None:
            return 0
        return len(self._message.signals)

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
        if index.column() in (COL_RAW, COL_PHYS):
            return base | Qt.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or self._message is None:
            return None
        sig = self._message.signals[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == COL_NAME:
                return sig.name
            if col == COL_RAW:
                return int(sig.raw_value)
            if col == COL_PHYS:
                return raw_to_physical(sig.raw_value, sig.scale, sig.offset)
            if col == COL_UNIT:
                return sig.unit
            if col == COL_MODE:
                return sig.sim_mode
        if role == Qt.TextAlignmentRole and col in (COL_RAW, COL_PHYS):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.FontRole and col in (COL_RAW, COL_PHYS):
            font = QFont("JetBrains Mono")
            font.setStyleHint(QFont.Monospace)
            font.setBold(True)
            return font
        if role == Qt.BackgroundRole and col in (COL_RAW, COL_PHYS):
            if index.row() in self._flashed_rows:
                return theme_color("accent-cyan", 42)
        return None

    # Sinyal: gerçek bir kullanıcı düzenlemesi tamamlandığında.
    user_edited = pyqtSignal()

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if role != Qt.EditRole or self._message is None:
            return False
        sig = self._message.signals[index.row()]
        col = index.column()
        try:
            if col == COL_RAW:
                sig.raw_value = int(value)
            elif col == COL_PHYS:
                sig.raw_value = physical_to_raw(float(value), sig.scale, sig.offset)
            else:
                return False
        except (TypeError, ValueError):
            return False
        # Hem raw hem phys hücresini yeniden boya.
        left = self.index(index.row(), COL_RAW)
        right = self.index(index.row(), COL_PHYS)
        self.dataChanged.emit(left, right, [Qt.DisplayRole])
        self.user_edited.emit()
        return True

    def flash_value_cells(self) -> None:
        if self._message is None or not self._message.signals:
            return
        self._flashed_rows = set(range(len(self._message.signals)))
        top = self.index(0, COL_RAW)
        bottom = self.index(len(self._message.signals) - 1, COL_PHYS)
        self.dataChanged.emit(top, bottom, [Qt.BackgroundRole])
        QTimer.singleShot(150, self.clear_value_flash)

    def clear_value_flash(self) -> None:
        if self._message is None or not self._flashed_rows:
            return
        rows = sorted(self._flashed_rows)
        self._flashed_rows.clear()
        top = self.index(rows[0], COL_RAW)
        bottom = self.index(rows[-1], COL_PHYS)
        self.dataChanged.emit(top, bottom, [Qt.BackgroundRole])


class SignalPanel(QWidget):

    signal_selected = pyqtSignal(object, object)  # (Message, Signal)
    message_modified = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.model = SignalTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMouseTracking(True)
        self.table.setItemDelegate(HmiTableDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hh = self.table.horizontalHeader()
        hh.setMinimumSectionSize(42)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_RAW, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_PHYS, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_UNIT, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_MODE, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        self.model.user_edited.connect(self.message_modified.emit)
        layout.addWidget(self.table, 1)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("Add Signal")
        self.btn_del = QPushButton("Delete Signal")
        self.btn_add.clicked.connect(self._add_signal)
        self.btn_del.clicked.connect(self._del_signal)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        layout.addLayout(btns)

        self.table.selectionModel().selectionChanged.connect(self._emit_selection)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_message(self, msg: Optional[Message]) -> None:
        self.model.set_message(msg)
        if msg and msg.signals:
            self.table.selectRow(0)
        else:
            self.signal_selected.emit(msg, None)

    def refresh(self) -> None:
        msg = self.model.message()
        if msg is None:
            return
        # Layoutchange yerine alt-üst yenile.
        top = self.model.index(0, 0)
        bot = self.model.index(max(0, len(msg.signals) - 1), len(COLS) - 1)
        self.model.dataChanged.emit(top, bot, [Qt.DisplayRole])

    def flash_value_cells(self) -> None:
        self.model.flash_value_cells()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _emit_selection(self, *_args) -> None:
        msg = self.model.message()
        rows = self.table.selectionModel().selectedRows()
        if not rows or msg is None:
            self.signal_selected.emit(msg, None)
            return
        idx = rows[0].row()
        if 0 <= idx < len(msg.signals):
            self.signal_selected.emit(msg, msg.signals[idx])
        else:
            self.signal_selected.emit(msg, None)

    def _add_signal(self) -> None:
        msg = self.model.message()
        if msg is None:
            return
        byte_pos, bit_pos = _first_free_byte_aligned_layout(msg)
        new_sig = Signal(
            name=f"Signal {len(msg.signals) + 1}",
            byte_pos=byte_pos,
            bit_pos=bit_pos,
            bit_length=8,
        )
        self.model.beginResetModel()
        msg.signals.append(new_sig)
        self.model.endResetModel()
        self.message_modified.emit()
        self.table.selectRow(len(msg.signals) - 1)

    def _del_signal(self) -> None:
        msg = self.model.message()
        if msg is None:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(msg.signals):
            self.model.beginResetModel()
            del msg.signals[idx]
            self.model.endResetModel()
            self.message_modified.emit()
            if msg.signals:
                self.table.selectRow(min(idx, len(msg.signals) - 1))
            else:
                self.signal_selected.emit(msg, None)


def _first_free_byte_aligned_layout(msg: Message) -> tuple[int, int]:
    used_bits: set[int] = set()
    for sig in msg.signals:
        try:
            used_bits.update(bit for bit in signal_bit_positions(sig) if 0 <= bit < 64)
        except Exception:
            continue

    for byte_pos in range(8):
        bits = set(range(byte_pos * 8, byte_pos * 8 + 8))
        if not bits & used_bits:
            return byte_pos, 0
    return 0, 0
