"""Small theme-aware line icons for the desktop command bar."""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap

from gui.theme import theme_color


def hmi_icon(name: str, size: int = 18) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(theme_color("accent-cyan"), 1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "new":
        _document(painter, size)
        painter.drawLine(QPointF(size * 0.50, size * 0.34), QPointF(size * 0.50, size * 0.68))
        painter.drawLine(QPointF(size * 0.33, size * 0.51), QPointF(size * 0.67, size * 0.51))
    elif name == "open":
        painter.drawPath(_folder_path(size))
    elif name == "save":
        _save(painter, size)
    elif name == "save_as":
        _save(painter, size)
        painter.drawLine(QPointF(size * 0.58, size * 0.28), QPointF(size * 0.74, size * 0.28))
        painter.drawLine(QPointF(size * 0.66, size * 0.20), QPointF(size * 0.66, size * 0.36))
    elif name == "recent":
        for y in (0.32, 0.50, 0.68):
            painter.drawLine(QPointF(size * 0.28, size * y), QPointF(size * 0.76, size * y))
            painter.drawPoint(QPointF(size * 0.18, size * y))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(size * 0.34, size * 0.24)
        path.lineTo(size * 0.34, size * 0.76)
        path.lineTo(size * 0.76, size * 0.50)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "stop":
        painter.drawRoundedRect(QRectF(size * 0.30, size * 0.30, size * 0.40, size * 0.40), 2, 2)
    elif name == "reconnect":
        rect = QRectF(size * 0.22, size * 0.22, size * 0.56, size * 0.56)
        painter.drawArc(rect, 35 * 16, 255 * 16)
        painter.drawLine(QPointF(size * 0.72, size * 0.23), QPointF(size * 0.78, size * 0.42))
        painter.drawLine(QPointF(size * 0.72, size * 0.23), QPointF(size * 0.55, size * 0.30))
    else:
        painter.drawEllipse(QRectF(size * 0.30, size * 0.30, size * 0.40, size * 0.40))

    painter.end()
    return QIcon(pixmap)


def _document(painter: QPainter, size: int) -> None:
    painter.drawRoundedRect(QRectF(size * 0.25, size * 0.16, size * 0.50, size * 0.68), 2, 2)


def _folder_path(size: int) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(size * 0.12, size * 0.34)
    path.lineTo(size * 0.38, size * 0.34)
    path.lineTo(size * 0.46, size * 0.24)
    path.lineTo(size * 0.82, size * 0.24)
    path.lineTo(size * 0.82, size * 0.76)
    path.lineTo(size * 0.12, size * 0.76)
    path.closeSubpath()
    return path


def _save(painter: QPainter, size: int) -> None:
    painter.drawRoundedRect(QRectF(size * 0.20, size * 0.16, size * 0.60, size * 0.68), 2, 2)
    painter.drawLine(QPointF(size * 0.34, size * 0.16), QPointF(size * 0.34, size * 0.40))
    painter.drawLine(QPointF(size * 0.34, size * 0.40), QPointF(size * 0.66, size * 0.40))
    painter.drawRoundedRect(QRectF(size * 0.34, size * 0.58, size * 0.32, size * 0.18), 1.5, 1.5)
