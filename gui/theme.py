"""Central HMI theme loader for the PyQt application."""

from __future__ import annotations

import ctypes
import re
import sys
from functools import lru_cache
from pathlib import Path

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QApplication, QWidget


THEME_QSS = Path(__file__).with_name("theme.qss")
_TOKEN_RE = re.compile(r"--([a-z0-9-]+):\s*([^;]+);", re.IGNORECASE)


@lru_cache(maxsize=1)
def theme_stylesheet() -> str:
    return THEME_QSS.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def theme_tokens() -> dict[str, str]:
    return {
        match.group(1): match.group(2).strip()
        for match in _TOKEN_RE.finditer(theme_stylesheet())
    }


def theme_color(name: str, alpha: int | None = None) -> QColor:
    value = theme_tokens()[name]
    color = _parse_qss_color(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def _parse_qss_color(value: str) -> QColor:
    if value.startswith("rgba(") and value.endswith(")"):
        parts = [part.strip() for part in value[5:-1].split(",")]
        if len(parts) == 4:
            red, green, blue = (int(parts[i]) for i in range(3))
            opacity = float(parts[3])
            return QColor(red, green, blue, round(opacity * 255))
    return QColor(value)


def apply_hmi_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, theme_color("bg-base"))
    palette.setColor(QPalette.WindowText, theme_color("text-primary"))
    palette.setColor(QPalette.Base, theme_color("bg-input"))
    palette.setColor(QPalette.AlternateBase, theme_color("bg-panel"))
    palette.setColor(QPalette.ToolTipBase, theme_color("bg-panel"))
    palette.setColor(QPalette.ToolTipText, theme_color("text-primary"))
    palette.setColor(QPalette.Text, theme_color("text-primary"))
    palette.setColor(QPalette.Button, theme_color("bg-panel"))
    palette.setColor(QPalette.ButtonText, theme_color("text-primary"))
    palette.setColor(QPalette.BrightText, theme_color("status-error"))
    palette.setColor(QPalette.Link, theme_color("accent-cyan"))
    palette.setColor(QPalette.Highlight, theme_color("accent-cyan", 60))
    palette.setColor(QPalette.HighlightedText, theme_color("text-primary"))
    palette.setColor(QPalette.Disabled, QPalette.Text, theme_color("text-disabled"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, theme_color("text-disabled"))
    app.setPalette(palette)
    app.setStyleSheet(theme_stylesheet())


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def apply_windows_dark_title_bar(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        dwm = ctypes.windll.dwmapi
        for attribute in (20, 19):
            result = dwm.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_int(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if result == 0:
                break
    except Exception:
        return
