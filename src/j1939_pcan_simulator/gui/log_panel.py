"""Frame log panel for recent transmit and error activity."""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, List, Tuple

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from j1939_pcan_simulator.protocol.frame_builder import format_bytes
from j1939_pcan_simulator.simulation.engine import DecodedSignal


MAX_LINES = 200


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: Deque[Tuple[str, str]] = deque(maxlen=MAX_LINES)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(QLabel("Frame Log"))
        header.addStretch(1)
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("All", "all")
        self.combo_filter.addItem("TX", "tx")
        self.combo_filter.addItem("RX", "rx")
        self.combo_filter.addItem("Error", "error")
        self.combo_filter.currentIndexChanged.connect(self._refresh_view)
        header.addWidget(self.combo_filter)
        self.edt_filter = QLineEdit()
        self.edt_filter.setPlaceholderText("CAN ID / PGN filter")
        self.edt_filter.setClearButtonEnabled(True)
        self.edt_filter.textChanged.connect(self._refresh_view)
        header.addWidget(self.edt_filter)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear)
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_LINES)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.view.setFont(font)
        layout.addWidget(self.view)

    # ------------------------------------------------------------------
    # Slot connected to the simulation engine frame_sent signal.
    # ------------------------------------------------------------------

    @pyqtSlot(float, str, bytes, list, bool)
    def append_frame(
        self,
        ts: float,
        can_id: str,
        data: bytes,
        decoded: List[DecodedSignal],
        sent_ok: bool,
    ) -> None:
        local = time.localtime(ts)
        ms = int((ts - int(ts)) * 1000)
        ts_str = time.strftime("%H:%M:%S", local) + f".{ms:03d}"
        bytes_str = format_bytes(data)
        sig_parts = []
        for d in decoded:
            unit = f" {d.unit}" if d.unit else ""
            phys = (
                f"{d.physical:.3f}".rstrip("0").rstrip(".")
                if isinstance(d.physical, float)
                else str(d.physical)
            )
            sig_parts.append(f"{d.name}={phys}{unit} (raw {d.raw})")
        sig_str = " | " + " ; ".join(sig_parts) if sig_parts else ""
        prefix = "TX" if sent_ok else "--"
        line = f"[{ts_str}] {prefix} {can_id}  {bytes_str}{sig_str}"
        self._append_line("tx" if sent_ok else "info", line)

    @pyqtSlot(str)
    def error(self, message: str) -> None:
        """Write an error message to the log panel."""
        ts = time.time()
        local = time.localtime(ts)
        ms = int((ts - int(ts)) * 1000)
        ts_str = time.strftime("%H:%M:%S", local) + f".{ms:03d}"
        # Keep multi-line tracebacks readable as one block.
        first_line, *rest = (message or "").rstrip().splitlines() or [""]
        lines = [f"[{ts_str}] !! ERROR: {first_line}"]
        for line in rest:
            lines.append(f"             {line}")
        self._append_line("error", "\n".join(lines))

    @pyqtSlot(str, str)
    def send_error(self, can_id: str, error_text: str) -> None:
        ts = time.time()
        local = time.localtime(ts)
        ms = int((ts - int(ts)) * 1000)
        ts_str = time.strftime("%H:%M:%S", local) + f".{ms:03d}"
        self._append_line("error", f"[{ts_str}] !! TX-FAIL {can_id}  {error_text}")

    def clear(self) -> None:
        self._lines.clear()
        self.view.clear()

    def _append_line(self, kind: str, line: str) -> None:
        self._lines.append((kind, line))
        if self._line_visible(kind, line):
            self.view.appendPlainText(line)

    def _refresh_view(self, *_args) -> None:
        self.view.clear()
        for kind, line in self._lines:
            if self._line_visible(kind, line):
                self.view.appendPlainText(line)

    def _line_visible(self, kind: str, line: str = "") -> bool:
        selected = self.combo_filter.currentData() or "all"
        if selected == "all":
            type_matches = True
        else:
            type_matches = selected == kind
        if not type_matches:
            return False
        needle = self.edt_filter.text().strip().upper()
        if not needle:
            return True
        return needle in line.upper()

