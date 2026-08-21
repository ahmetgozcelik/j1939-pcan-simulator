"""Mini oscilloscope widget for the selected signal preview."""

from __future__ import annotations

from collections import deque
from typing import Optional

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

from j1939_pcan_simulator.config.workspace import Signal
from j1939_pcan_simulator.protocol.frame_builder import raw_to_physical
from j1939_pcan_simulator.gui.theme import theme_color


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._signal: Optional[Signal] = None
        self._values: deque[float] = deque(maxlen=80)
        self.setMinimumHeight(86)
        self.setToolTip("Live selected-signal waveform preview")

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.sample_now)
        self._timer.start()

    def set_signal(self, signal: Optional[Signal]) -> None:
        self._signal = signal
        self._values.clear()
        self.sample_now()

    def sample_now(self) -> None:
        if self._signal is None:
            self.update()
            return
        try:
            value = raw_to_physical(
                self._signal.raw_value,
                self._signal.scale,
                self._signal.offset,
            )
        except Exception:
            value = float(self._signal.raw_value)
        self._values.append(float(value))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(rect, theme_color("bg-input"))

        painter.setPen(QPen(theme_color("border-subtle"), 1))
        painter.drawRoundedRect(rect, 5, 5)

        grid_pen = QPen(theme_color("border-subtle"), 1)
        grid_pen.setStyle(Qt.DotLine)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = rect.top() + int(rect.height() * i / 4)
            painter.drawLine(rect.left() + 8, y, rect.right() - 8, y)
        for i in range(1, 6):
            x = rect.left() + int(rect.width() * i / 6)
            painter.drawLine(x, rect.top() + 8, x, rect.bottom() - 8)

        if len(self._values) < 2:
            painter.setPen(theme_color("text-secondary"))
            painter.drawText(rect, Qt.AlignCenter, "WAVEFORM")
            return

        low = min(self._values)
        high = max(self._values)
        if abs(high - low) < 1e-9:
            low -= 1.0
            high += 1.0

        plot = rect.adjusted(10, 10, -10, -10)
        step = plot.width() / max(1, len(self._values) - 1)
        path = QPainterPath()
        for i, value in enumerate(self._values):
            x = plot.left() + i * step
            normalized = (value - low) / (high - low)
            y = plot.bottom() - normalized * plot.height()
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(theme_color("accent-cyan", 58), 5))
        painter.drawPath(path)
        painter.setPen(QPen(theme_color("accent-cyan"), 1.8))
        painter.drawPath(path)

        label = f"{self._values[-1]:.4g}"
        painter.setPen(theme_color("text-secondary"))
        painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignTop | Qt.AlignRight, label)

