"""Uygulama giriş noktası.

Dark tema palet + QSS uygular ve MainWindow'u açar.
"""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

from error_reporter import get_reporter, install_global_excepthook
from gui.main_window import MainWindow


# Fusion + koyu palet, üzerine biraz QSS bindiriyoruz.
DARK_QSS = """
QWidget {
    font-size: 10pt;
}
QToolBar {
    spacing: 6px;
    padding: 4px;
}
QTableView {
    gridline-color: #3a3a3a;
    selection-background-color: #2a82da;
    selection-color: white;
    alternate-background-color: #2b2b2b;
}
QHeaderView::section {
    background-color: #2b2b2b;
    color: #dddddd;
    padding: 4px;
    border: 1px solid #3a3a3a;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #2b2b2b;
    border: 1px solid #3a3a3a;
    padding: 3px 5px;
    border-radius: 3px;
}
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #4a4a4a;
    padding: 5px 12px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #2a82da;
}
QPushButton:disabled {
    color: #666666;
    background-color: #2b2b2b;
}
QPlainTextEdit {
    background-color: #1e1e1e;
    color: #dddddd;
    font-family: Consolas, "Courier New", monospace;
}
QGroupBox {
    border: 1px solid #3a3a3a;
    margin-top: 12px;
    padding-top: 6px;
    border-radius: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLabel#statusLed {
    border-radius: 7px;
    min-width: 14px;
    max-width: 14px;
    min-height: 14px;
    max-height: 14px;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(58, 58, 58))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    app.setPalette(palette)
    app.setStyleSheet(DARK_QSS)


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("J1939 PCAN Simulator")
    apply_dark_theme(app)

    # Hata raporlayıcı önce kurulsun, MainWindow init sırasında oluşan
    # potansiyel hatalar bile log paneline akabilsin.
    reporter = get_reporter()
    install_global_excepthook(reporter)

    win = MainWindow(reporter=reporter)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
