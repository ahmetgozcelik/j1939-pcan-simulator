"""Çalışma alanı (workspace) veri modeli ve JSON kaydet/yükle."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, List, Optional

from j1939_id import is_dm1_can_id


CURRENT_VERSION = "1.0"

APP_DIR = Path.home() / ".j1939_simulator"
RECENT_FILE = APP_DIR / "recent.json"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "configs" / "default.json"
AUTOSAVE_PATH = APP_DIR / "autosave.json"


VALID_BYTE_ORDERS = ("little_endian", "big_endian")
VALID_SIM_MODES = ("fixed", "random", "sine", "sawtooth", "ramp")


@dataclass
class Signal:
    name: str = "New Signal"
    byte_pos: int = 0
    bit_pos: int = 0
    bit_length: int = 8
    byte_order: str = "little_endian"
    scale: float = 1.0
    offset: float = 0.0
    raw_min: int = 0
    raw_max: int = 255
    raw_value: int = 0
    sim_mode: str = "fixed"
    unit: str = ""
    sine_period_s: float = 10.0
    ramp_step: Optional[float] = None
    ramp_period_s: float = 10.0

    def physical(self) -> float:
        return self.raw_value * self.scale + self.offset

    def physical_min(self) -> float:
        return self.raw_min * self.scale + self.offset

    def physical_max(self) -> float:
        return self.raw_max * self.scale + self.offset


@dataclass
class DM1Config:
    """DM1 mesajının simülasyon konfigürasyonu - JSON'a kaydedilir."""
    lamp_status: int = 0x00
    lamp_mode: str = "fixed"
    auto_lamp_interval_s: float = 2.0
    fmi: int = 0
    occurrence: int = 0
    spn: int = 0
    spn_mode: str = "fixed"
    spn_list: List[int] = field(default_factory=list)
    spn_list_interval_s: float = 2.0
    spn_range_min: int = 0
    spn_range_max: int = 1000
    spn_range_interval_s: float = 2.0


@dataclass
class Message:
    can_id: str = "18FFFFFF"
    name: str = "New Message"
    cycle_ms: int = 1000
    active: bool = False
    signals: List[Signal] = field(default_factory=list)
    dm1_config: Optional[DM1Config] = None  # Sadece DM1 mesajları için

    def can_id_int(self) -> int:
        return int(self.can_id, 16)

    def is_dm1(self) -> bool:
        return is_dm1_can_id(self.can_id)


@dataclass
class Workspace:
    version: str = CURRENT_VERSION
    messages: List[Message] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _signal_from_dict(d: dict) -> Signal:
    sim_mode = str(d.get("sim_mode", "fixed"))
    ramp_step = float(d["ramp_step"]) if d.get("ramp_step") is not None else None
    if sim_mode == "ramp" and ramp_step is not None and "ramp_period_s" not in d:
        sim_mode = "sawtooth"
    return Signal(
        name=d.get("name", "Signal"),
        byte_pos=int(d.get("byte_pos", 0)),
        bit_pos=int(d.get("bit_pos", 0)),
        bit_length=int(d.get("bit_length", 8)),
        byte_order=str(d.get("byte_order", "little_endian")),
        scale=float(d.get("scale", 1.0)),
        offset=float(d.get("offset", 0.0)),
        raw_min=int(d.get("raw_min", 0)),
        raw_max=int(d.get("raw_max", 255)),
        raw_value=int(d.get("raw_value", 0)),
        sim_mode=sim_mode,
        unit=str(d.get("unit", "")),
        sine_period_s=float(d.get("sine_period_s", 10.0)),
        ramp_step=ramp_step,
        ramp_period_s=float(d.get("ramp_period_s", 10.0)),
    )


def _dm1_config_from_dict(d: dict) -> DM1Config:
    return DM1Config(
        lamp_status=int(d.get("lamp_status", 0x00)),
        lamp_mode=str(d.get("lamp_mode", "fixed")),
        auto_lamp_interval_s=float(d.get("auto_lamp_interval_s", 2.0)),
        fmi=int(d.get("fmi", 0)),
        occurrence=int(d.get("occurrence", 0)),
        spn=int(d.get("spn", 0)),
        spn_mode=str(d.get("spn_mode", "fixed")),
        spn_list=[int(x) for x in d.get("spn_list", [])],
        spn_list_interval_s=float(d.get("spn_list_interval_s", 2.0)),
        spn_range_min=int(d.get("spn_range_min", 0)),
        spn_range_max=int(d.get("spn_range_max", 1000)),
        spn_range_interval_s=float(d.get("spn_range_interval_s", 2.0)),
    )


def _dm1_config_to_dict(c: DM1Config) -> dict:
    return {
        "lamp_status": c.lamp_status,
        "lamp_mode": c.lamp_mode,
        "auto_lamp_interval_s": c.auto_lamp_interval_s,
        "fmi": c.fmi,
        "occurrence": c.occurrence,
        "spn": c.spn,
        "spn_mode": c.spn_mode,
        "spn_list": c.spn_list,
        "spn_list_interval_s": c.spn_list_interval_s,
        "spn_range_min": c.spn_range_min,
        "spn_range_max": c.spn_range_max,
        "spn_range_interval_s": c.spn_range_interval_s,
    }


def _message_from_dict(d: dict) -> Message:
    dm1_config = None
    if d.get("dm1_config"):
        dm1_config = _dm1_config_from_dict(d["dm1_config"])
    return Message(
        can_id=str(d.get("can_id", "18FFFFFF")).upper(),
        name=d.get("name", "Message"),
        cycle_ms=int(d.get("cycle_ms", 1000)),
        active=bool(d.get("active", False)),
        signals=[_signal_from_dict(s) for s in d.get("signals", [])],
        dm1_config=dm1_config,
    )


def workspace_from_dict(d: dict) -> Workspace:
    return Workspace(
        version=str(d.get("version", CURRENT_VERSION)),
        messages=[_message_from_dict(m) for m in d.get("messages", [])],
    )


def workspace_to_dict(ws: Workspace) -> dict:
    messages = []
    for m in ws.messages:
        msg_dict = {
            "can_id": m.can_id.upper(),
            "name": m.name,
            "cycle_ms": int(m.cycle_ms),
            "active": bool(m.active),
            "signals": [asdict(s) for s in m.signals],
        }
        if m.dm1_config is not None:
            msg_dict["dm1_config"] = _dm1_config_to_dict(m.dm1_config)
        messages.append(msg_dict)
    return {"version": ws.version, "messages": messages}


def load(path: str | os.PathLike) -> Workspace:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return workspace_from_dict(data)


def save(path: str | os.PathLike, ws: Workspace) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(workspace_to_dict(ws), f, indent=2, ensure_ascii=False)


def default_workspace() -> Workspace:
    if DEFAULT_CONFIG.exists():
        try:
            return load(DEFAULT_CONFIG)
        except Exception:
            pass
    return Workspace(version=CURRENT_VERSION, messages=[])


def clone_signal(s: Signal) -> Signal:
    return replace(s)


def clone_message(m: Message) -> Message:
    return Message(
        can_id=m.can_id,
        name=m.name,
        cycle_ms=m.cycle_ms,
        active=m.active,
        signals=[clone_signal(s) for s in m.signals],
        dm1_config=replace(m.dm1_config) if m.dm1_config else None,
    )


# ---------------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------------

@dataclass
class RecentState:
    last_config_path: Optional[str] = None
    recent: List[str] = field(default_factory=list)


def _read_recent() -> RecentState:
    if not RECENT_FILE.exists():
        return RecentState()
    try:
        with RECENT_FILE.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return RecentState(
            last_config_path=data.get("last_config_path"),
            recent=list(data.get("recent", [])),
        )
    except Exception:
        return RecentState()


def _write_recent(state: RecentState) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with RECENT_FILE.open("w", encoding="utf-8") as f:
            json.dump(
                {"last_config_path": state.last_config_path, "recent": state.recent},
                f, indent=2,
            )
    except Exception:
        pass


def get_last_config_path() -> Optional[str]:
    return _read_recent().last_config_path


def get_recent_files(max_entries: int = 8) -> List[str]:
    return _read_recent().recent[:max_entries]


def remember_path(path: str, max_entries: int = 8) -> None:
    state = _read_recent()
    p = str(Path(path).resolve())
    state.last_config_path = p
    if p in state.recent:
        state.recent.remove(p)
    state.recent.insert(0, p)
    state.recent = state.recent[:max_entries]
    _write_recent(state)


# ---------------------------------------------------------------------------
# Config IO Worker
# ---------------------------------------------------------------------------

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
except ImportError:
    QObject = None
    QThread = None

if QObject is not None:

    class ConfigIOWorker(QObject):
        request_load = pyqtSignal(str)
        request_save = pyqtSignal(str, dict)

        loaded = pyqtSignal(str, object)
        saved = pyqtSignal(str)
        failed = pyqtSignal(str, str, str)

        def __init__(self, parent: Optional[QObject] = None):
            super().__init__(parent)
            self._thread = QThread()
            self._thread.setObjectName("ConfigIOThread")
            self.moveToThread(self._thread)
            self.request_load.connect(self._do_load)
            self.request_save.connect(self._do_save)

        def start(self) -> None:
            if not self._thread.isRunning():
                self._thread.start()

        def shutdown(self, wait_ms: int = 2000) -> None:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(wait_ms)

        @pyqtSlot(str)
        def _do_load(self, path: str) -> None:
            try:
                ws = load(path)
                self.loaded.emit(path, ws)
            except Exception as exc:
                self.failed.emit("load", path, str(exc))

        @pyqtSlot(str, dict)
        def _do_save(self, path: str, ws_dict: dict) -> None:
            try:
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("w", encoding="utf-8") as f:
                    json.dump(ws_dict, f, indent=2, ensure_ascii=False)
                self.saved.emit(path)
            except Exception as exc:
                self.failed.emit("save", path, str(exc))
