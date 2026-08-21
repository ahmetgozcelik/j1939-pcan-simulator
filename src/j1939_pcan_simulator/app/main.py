"""Application entry point."""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from j1939_pcan_simulator.app.error_reporter import (
    get_reporter,
    install_global_excepthook,
)
from j1939_pcan_simulator.gui.main_window import MainWindow
from j1939_pcan_simulator.gui.theme import (
    apply_hmi_theme,
    apply_windows_dark_title_bar,
)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("J1939 PCAN Simulator")
    apply_hmi_theme(app)

    reporter = get_reporter()
    install_global_excepthook(reporter)

    win = MainWindow(reporter=reporter)
    win.show()
    apply_windows_dark_title_bar(win)
    return app.exec_()


