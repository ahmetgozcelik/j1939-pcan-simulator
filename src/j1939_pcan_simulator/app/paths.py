"""Filesystem helpers for source and bundled application layouts."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the runtime root for repository runs and PyInstaller bundles."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[3]


def config_path(filename: str) -> Path:
    return app_root() / "configs" / filename

