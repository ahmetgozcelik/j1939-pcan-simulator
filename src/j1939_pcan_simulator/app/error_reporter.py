"""Single error-reporting point for uncaught exceptions.

This lives outside ``main.py`` because the launcher is loaded as ``__main__``.
Importing from the launcher in other modules could execute application startup
code a second time.
"""

from __future__ import annotations

import sys
import threading
import traceback
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal


class ErrorReporter(QObject):
    """Single process-wide error reporter.

    Emitting ``error_logged`` is safe from any thread as long as connected UI
    slots use queued connections.
    """

    error_logged = pyqtSignal(str)


_reporter_singleton: Optional[ErrorReporter] = None


def get_reporter() -> ErrorReporter:
    """Return the lazily created process-wide reporter."""
    global _reporter_singleton
    if _reporter_singleton is None:
        _reporter_singleton = ErrorReporter()
    return _reporter_singleton


def install_global_excepthook(reporter: ErrorReporter) -> None:
    """Install ``sys.excepthook`` and ``threading.excepthook``."""

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
        # Also write to stderr for console-based debugging.
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
    """Emit a known error message through the global reporter."""
    try:
        get_reporter().error_logged.emit(message)
    except Exception:
        try:
            sys.__stderr__.write(message)
        except Exception:
            pass

