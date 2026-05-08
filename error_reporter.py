"""Yakalanmamış istisnaları log paneline ileten tek noktalı raporlayıcı.

Ayrı bir modül olarak ayrılmıştır çünkü ``main.py`` giriş noktası olarak
``__main__`` adıyla yüklenir; başka modüller ``from main import ...`` yaparsa
modül yeniden çalıştırılırdı.
"""

from __future__ import annotations

import sys
import threading
import traceback
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal


class ErrorReporter(QObject):
    """Tek noktalı hata raporlayıcı.

    ``error_logged`` sinyaline bağlanan slot'lar (örn. ``LogPanel.error``)
    queued connection ile çağrıldığı sürece herhangi bir thread'den emit
    güvenlidir.
    """

    error_logged = pyqtSignal(str)


_reporter_singleton: Optional[ErrorReporter] = None


def get_reporter() -> ErrorReporter:
    """Süreç boyunca tek olan raporlayıcıyı döner (lazy)."""
    global _reporter_singleton
    if _reporter_singleton is None:
        _reporter_singleton = ErrorReporter()
    return _reporter_singleton


def install_global_excepthook(reporter: ErrorReporter) -> None:
    """``sys.excepthook`` ve ``threading.excepthook`` 'u kurar."""

    def _format(exc_type, exc_value, exc_tb) -> str:
        return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    def _hook(exc_type, exc_value, exc_tb):
        try:
            msg = _format(exc_type, exc_value, exc_tb)
        except Exception:
            msg = f"{exc_type}: {exc_value}"
        try:
            reporter.error_logged.emit(msg)
        except Exception:
            pass
        # stderr'e de yaz: konsoldan takip etmek isteyenler için.
        try:
            sys.__stderr__.write(msg)
        except Exception:
            pass

    def _thread_hook(args):  # threading.ExceptHookArgs
        _hook(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = _hook
    try:
        threading.excepthook = _thread_hook  # Python 3.8+
    except Exception:
        pass


def report(message: str) -> None:
    """Bilinen hata metnini global raporlayıcıya yollar."""
    try:
        get_reporter().error_logged.emit(message)
    except Exception:
        try:
            sys.__stderr__.write(message)
        except Exception:
            pass
