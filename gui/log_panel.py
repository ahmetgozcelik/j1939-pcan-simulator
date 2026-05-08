"""Gönderilen son ~100 çerçeveyi gösteren basit log paneli."""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, List

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frame_builder import format_bytes
from simulator_engine import DecodedSignal


MAX_LINES = 200  # Hata satırları için biraz daha geniş tutalım


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: Deque[str] = deque(maxlen=MAX_LINES)
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
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear)
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_LINES)
        layout.addWidget(self.view)

    # ------------------------------------------------------------------
    # Slot: motor frame_sent sinyalinden bağlanır
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
        self.view.appendPlainText(line)

    @pyqtSlot(str)
    def error(self, message: str) -> None:
        """Hata mesajını log paneline yazar (yakalanmamış istisnalar için)."""
        ts = time.time()
        local = time.localtime(ts)
        ms = int((ts - int(ts)) * 1000)
        ts_str = time.strftime("%H:%M:%S", local) + f".{ms:03d}"
        # Çok satırlı hatalar tek bir blokta okunsun.
        first_line, *rest = (message or "").rstrip().splitlines() or [""]
        self.view.appendPlainText(f"[{ts_str}] !! ERROR: {first_line}")
        for line in rest:
            self.view.appendPlainText(f"             {line}")

    @pyqtSlot(str, str)
    def send_error(self, can_id: str, error_text: str) -> None:
        ts = time.time()
        local = time.localtime(ts)
        ms = int((ts - int(ts)) * 1000)
        ts_str = time.strftime("%H:%M:%S", local) + f".{ms:03d}"
        self.view.appendPlainText(
            f"[{ts_str}] !! TX-FAIL {can_id}  {error_text}"
        )

    def clear(self) -> None:
        self.view.clear()
