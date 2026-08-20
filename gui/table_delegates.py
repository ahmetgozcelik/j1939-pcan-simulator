"""Custom table painting for the HMI operator workspace."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFont, QPen
from PyQt5.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from gui.theme import theme_color


ROLE_ACTIVE_STATE = Qt.UserRole + 41
ROLE_TYPE_KIND = Qt.UserRole + 42


class HmiTableDelegate(QStyledItemDelegate):
    """Paint selected rows with an accent strip instead of the native blue block."""

    def paint(self, painter, option, index) -> None:
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            painter.save()
            fill = theme_color("accent-cyan", 34 if selected else 18)
            painter.fillRect(option.rect, fill)
            if selected:
                strip = option.rect.adjusted(0, 0, -option.rect.width() + 3, 0)
                painter.fillRect(strip, theme_color("accent-cyan"))
            painter.restore()

        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.State_Selected
        super().paint(painter, opt, index)


class MessageTableDelegate(HmiTableDelegate):
    def __init__(self, active_column: int, type_column: int, parent=None):
        super().__init__(parent)
        self.active_column = active_column
        self.type_column = type_column

    def paint(self, painter, option, index) -> None:
        if index.column() == self.active_column:
            self._paint_active_led(painter, option, index)
            return
        if index.column() == self.type_column:
            self._paint_type_badge(painter, option, index)
            return
        super().paint(painter, option, index)

    def _paint_active_led(self, painter, option, index) -> None:
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.save()
        if selected or hovered:
            painter.fillRect(
                option.rect,
                theme_color("accent-cyan", 34 if selected else 18),
            )
            if selected:
                painter.fillRect(
                    option.rect.adjusted(0, 0, -option.rect.width() + 3, 0),
                    theme_color("accent-cyan"),
                )

        on = bool(index.data(ROLE_ACTIVE_STATE))
        size = 13
        rect = QRectF(
            option.rect.center().x() - size / 2,
            option.rect.center().y() - size / 2,
            size,
            size,
        )
        if on:
            glow = QRectF(rect).adjusted(-4, -4, 4, 4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme_color("status-ok", 42))
            painter.drawEllipse(glow)
            painter.setBrush(theme_color("status-ok"))
            painter.drawEllipse(rect)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(theme_color("text-disabled"), 1.4))
            painter.drawEllipse(rect)
        painter.restore()

    def _paint_type_badge(self, painter, option, index) -> None:
        text = str(index.data(Qt.DisplayRole) or "")
        if not text:
            super().paint(painter, option, index)
            return

        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            painter.fillRect(
                option.rect,
                theme_color("accent-cyan", 34 if selected else 18),
            )
            if selected:
                painter.fillRect(
                    option.rect.adjusted(0, 0, -option.rect.width() + 3, 0),
                    theme_color("accent-cyan"),
                )

        category = str(index.data(ROLE_TYPE_KIND) or text)
        if category == "diagnostic":
            border = theme_color("status-warn")
            fill = theme_color("status-warn", 32)
            color = theme_color("status-warn")
        elif category in {"request", "transport"}:
            border = theme_color("accent-cyan")
            fill = theme_color("accent-cyan", 28)
            color = theme_color("accent-cyan")
        elif category == "invalid":
            border = theme_color("status-error")
            fill = theme_color("status-error", 32)
            color = theme_color("status-error")
        else:
            border = theme_color("border-strong")
            fill = theme_color("bg-panel-hover")
            color = theme_color("text-secondary")

        font = QFont(option.font)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = min(option.rect.width() - 8, metrics.horizontalAdvance(text) + 18)
        rect = QRectF(
            option.rect.left() + 6,
            option.rect.center().y() - 10,
            max(42, width),
            20,
        )
        painter.setPen(QPen(border, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()
