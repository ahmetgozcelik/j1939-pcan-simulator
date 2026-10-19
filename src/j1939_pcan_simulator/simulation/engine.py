"""Simulation engine that runs one ``QThread`` per message."""

from __future__ import annotations

import math
import random
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal

from j1939_pcan_simulator.transport.can_bus import PCanInterface
from j1939_pcan_simulator.config.workspace import DTCEntry, Message, Signal
from j1939_pcan_simulator.protocol.dm_definitions import auto_lamp_steps, build_lamp_status, load_dm1_definitions
from j1939_pcan_simulator.protocol.frame_builder import (
    DiagnosticTroubleCode,
    build_dm1_frame,
    build_dm1_multi_dtc,
    build_frame,
    clamp_raw,
)


@dataclass
class DecodedSignal:
    name: str
    raw: int
    physical: float
    unit: str


# ---------------------------------------------------------------------------
# DM1 state with extended simulation modes
# ---------------------------------------------------------------------------

@dataclass
class DM1State:
    lamp_status: int = 0x00
    flash_lamp_status: int = 0xFF
    spn: int = 0
    fmi: int = 0
    occurrence: int = 0

    # Simulation modes
    spn_mode: str = "fixed"          # "fixed" | "list" | "random_range" | "multi_dtc"
    lamp_mode: str = "fixed"         # "fixed" | "auto"

    # SPN list mode
    spn_list: List[int] = field(default_factory=list)
    spn_list_interval_s: float = 2.0
    _spn_list_index: int = field(default=0, repr=False)
    _spn_list_last_change: float = field(default=0.0, repr=False)

    # SPN random range mode
    spn_range_min: int = 0
    spn_range_max: int = 524287
    spn_range_interval_s: float = 2.0
    _spn_range_last_change: float = field(default=0.0, repr=False)

    # Auto lamp cycle
    auto_lamp_interval_s: float = 2.0
    _auto_lamp_index: int = field(default=0, repr=False)
    _auto_lamp_last_change: float = field(default=0.0, repr=False)

    # Multi DTC fault list
    dtc_list: List[DTCEntry] = field(default_factory=list)


class MessageRunner(QThread):
    frame_sent = pyqtSignal(float, str, bytes, list, bool)
    send_request = pyqtSignal(int, bytes)
    error_logged = pyqtSignal(str)

    def __init__(self, message: Message, engine: "SimulatorEngine", parent=None):
        super().__init__(parent)
        self.setObjectName(f"MsgRunner[{message.can_id}]")
        self.message = message
        self.engine = engine
        self._stop_evt = threading.Event()
        self._ramp_state: Dict[int, float] = {}
        self._start_monotonic = 0.0

    def stop(self) -> None:
        self._stop_evt.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            self._loop()
        except Exception:
            tb = traceback.format_exc()
            self.error_logged.emit(f"MessageRunner[{self.message.can_id}] crashed:\n{tb}")

    def _loop(self) -> None:
        cycle_s = max(0.001, self.message.cycle_ms / 1000.0)
        self._start_monotonic = time.monotonic()
        next_tick = self._start_monotonic
        while not self._stop_evt.is_set() and not self.isInterruptionRequested():
            now = time.monotonic()
            t = now - self._start_monotonic
            try:
                self._tick(t)
            except Exception:
                tb = traceback.format_exc()
                self.error_logged.emit(f"Tick error in {self.message.can_id}:\n{tb}")
            next_tick += cycle_s
            sleep_for = next_tick - time.monotonic()
            if sleep_for < 0:
                next_tick = time.monotonic()
                sleep_for = 0
            if self._stop_evt.wait(sleep_for):
                break

    def _tick(self, t: float) -> None:
        # frames_to_send: list of (can_id_int, can_id_hex, data, decoded)
        frames_to_send: List[tuple] = []
        use_bam_delay = False

        with self.engine.lock:
            msg = self.message
            decoded: List[DecodedSignal] = []
            overrides: Dict[int, int] = {}

            if msg.is_diagnostic_dtc():
                state = self.engine.dm1_states.get(msg.can_id)
                if state is None:
                    state = DM1State()
                    self.engine.dm1_states[msg.can_id] = state

                now = time.monotonic()
                effective_spn = state.spn
                effective_lamp = state.lamp_status

                if state.spn_mode == "list" and state.spn_list:
                    elapsed = now - state._spn_list_last_change
                    if elapsed >= state.spn_list_interval_s:
                        state._spn_list_index = (state._spn_list_index + 1) % len(state.spn_list)
                        state._spn_list_last_change = now
                    effective_spn = state.spn_list[state._spn_list_index]

                elif state.spn_mode == "random_range":
                    elapsed = now - state._spn_range_last_change
                    if elapsed >= state.spn_range_interval_s:
                        effective_spn = random.randint(
                            min(state.spn_range_min, state.spn_range_max),
                            max(state.spn_range_min, state.spn_range_max)
                        )
                        state.spn = effective_spn
                        state._spn_range_last_change = now

                if state.lamp_mode == "auto":
                    auto_steps = auto_lamp_steps(self.engine.dm1_definitions)
                    state._auto_lamp_index %= len(auto_steps)
                    elapsed = now - state._auto_lamp_last_change
                    if elapsed >= state.auto_lamp_interval_s:
                        state._auto_lamp_index = (state._auto_lamp_index + 1) % len(auto_steps)
                        effective_lamp = build_lamp_status(
                            auto_steps[state._auto_lamp_index],
                            self.engine.dm1_definitions,
                        )
                        state._auto_lamp_last_change = now
                    else:
                        effective_lamp = build_lamp_status(
                            auto_steps[state._auto_lamp_index],
                            self.engine.dm1_definitions,
                        )

                if state.spn_mode == "multi_dtc":
                    active_dtcs = [
                        DiagnosticTroubleCode(e.spn, e.fmi, e.oc)
                        for e in state.dtc_list
                        if e.active
                    ]
                    raw_frames = build_dm1_multi_dtc(
                        effective_lamp,
                        active_dtcs,
                        state.flash_lamp_status,
                        msg.can_id_int(),
                    )
                    use_bam_delay = len(active_dtcs) >= 2
                    dtc_desc = " | ".join(
                        f"SPN={d.spn} FMI={d.fmi} OC={d.occurrence_count}"
                        for d in active_dtcs
                    )
                    for i, (cid_int, frame_data) in enumerate(raw_frames):
                        cid_hex = f"{cid_int:08X}"
                        if i == 0 and use_bam_delay:
                            dec = [DecodedSignal(
                                name="DM1-BAM",
                                raw=len(active_dtcs),
                                physical=float(len(active_dtcs)),
                                unit=dtc_desc or "no active DTCs",
                            )]
                        elif use_bam_delay:
                            dec = [DecodedSignal(name=f"BAM-DT{i}", raw=i, physical=float(i), unit="")]
                        else:
                            # single frame (0 or 1 DTC)
                            dec_spn = active_dtcs[0].spn if active_dtcs else 0
                            dec_fmi = active_dtcs[0].fmi if active_dtcs else 0
                            dec_oc = active_dtcs[0].occurrence_count if active_dtcs else 0
                            dec = [DecodedSignal(
                                name="DM1",
                                raw=dec_spn,
                                physical=float(dec_spn),
                                unit=f"FMI={dec_fmi} OC={dec_oc}",
                            )]
                        frames_to_send.append((cid_int, cid_hex, frame_data, dec))
                else:
                    data = build_dm1_frame(
                        effective_lamp,
                        effective_spn,
                        state.fmi,
                        state.occurrence,
                        flash_lamp_status=state.flash_lamp_status,
                    )
                    decoded.append(DecodedSignal(
                        name="DM1",
                        raw=effective_spn,
                        physical=float(effective_spn),
                        unit=f"FMI={state.fmi} OC={state.occurrence}",
                    ))
                    frames_to_send.append((msg.can_id_int(), msg.can_id, data, decoded))
            else:
                for sig in msg.signals:
                    raw = self._next_raw(sig, t)
                    raw = clamp_raw(raw, sig)
                    overrides[id(sig)] = raw
                    decoded.append(DecodedSignal(
                        name=sig.name,
                        raw=raw,
                        physical=raw * sig.scale + sig.offset,
                        unit=sig.unit,
                    ))
                data = build_frame(msg, raw_overrides=overrides)
                for sig in msg.signals:
                    if sig.sim_mode != "fixed" and id(sig) in overrides:
                        sig.raw_value = overrides[id(sig)]
                frames_to_send.append((msg.can_id_int(), msg.can_id, data, decoded))

        for i, (cid_int, cid_hex, frame_data, dec) in enumerate(frames_to_send):
            self.send_request.emit(cid_int, frame_data)
            self.frame_sent.emit(time.time(), cid_hex, frame_data, dec, True)
            if use_bam_delay and i < len(frames_to_send) - 1:
                self._stop_evt.wait(0.050)

    def _next_raw(self, sig: Signal, t: float) -> int:
        mode = sig.sim_mode
        lo = min(sig.raw_min, sig.raw_max)
        hi = max(sig.raw_min, sig.raw_max)
        if mode == "fixed" or lo == hi:
            return sig.raw_value
        if mode == "random":
            return random.randint(lo, hi)
        if mode == "sine":
            period = sig.sine_period_s if sig.sine_period_s > 0 else 10.0
            mid = (lo + hi) / 2.0
            amp = (hi - lo) / 2.0
            return int(round(mid + amp * math.sin(2 * math.pi * t / period)))
        if mode == "sawtooth":
            step = sig.ramp_step
            if step is None or step == 0:
                step = (hi - lo) / 100.0 if hi != lo else 1.0
            cur = self._ramp_state.get(id(sig), float(sig.raw_value))
            cur += step
            if cur > hi:
                cur = float(lo)
            elif cur < lo:
                cur = float(hi)
            self._ramp_state[id(sig)] = cur
            return int(round(cur))
        if mode == "ramp":
            period = sig.ramp_period_s if sig.ramp_period_s > 0 else 10.0
            half = period / 2.0
            phase = t % period
            if phase < half:
                frac = phase / half
            else:
                frac = 1.0 - (phase - half) / half
            return int(round(lo + (hi - lo) * frac))
        return sig.raw_value


class SimulatorEngine(QObject):
    frame_sent = pyqtSignal(float, str, bytes, list, bool)
    error_logged = pyqtSignal(str)
    frame_send_error = pyqtSignal(str, str)

    def __init__(self, pcan: PCanInterface, parent=None):
        super().__init__(parent)
        self.pcan = pcan
        self.lock = threading.RLock()
        self._runners: Dict[str, MessageRunner] = {}
        self.dm1_states: Dict[str, DM1State] = {}
        self.dm1_definitions = load_dm1_definitions()
        self.pcan.send_failed.connect(self.frame_send_error, Qt.QueuedConnection)

    def start_message(self, msg: Message) -> None:
        with self.lock:
            existing = self._runners.get(msg.can_id)
            if existing is not None and existing.isRunning():
                existing.stop()
                existing.wait(500)
            runner = MessageRunner(msg, self)
            runner.send_request.connect(self.pcan._do_send, Qt.QueuedConnection)
            runner.frame_sent.connect(self.frame_sent, Qt.QueuedConnection)
            runner.error_logged.connect(self.error_logged, Qt.QueuedConnection)
            self._runners[msg.can_id] = runner
        runner.start()

    def stop_message(self, can_id: str) -> None:
        with self.lock:
            runner = self._runners.pop(can_id, None)
        if runner is not None:
            runner.stop()
            runner.wait(500)

    def stop_all(self) -> None:
        with self.lock:
            runners = list(self._runners.values())
            self._runners.clear()
        for r in runners:
            r.stop()
        for r in runners:
            r.wait(500)

    def is_running(self, can_id: str) -> bool:
        with self.lock:
            r = self._runners.get(can_id)
            return r is not None and r.isRunning()

    def running_ids(self) -> List[str]:
        with self.lock:
            return [cid for cid, r in self._runners.items() if r.isRunning()]

    def get_dm1_state(self, can_id: str) -> DM1State:
        with self.lock:
            state = self.dm1_states.get(can_id)
            if state is None:
                state = DM1State()
                self.dm1_states[can_id] = state
            return state

    def set_dm1_state(self, can_id: str, state: DM1State) -> None:
        with self.lock:
            self.dm1_states[can_id] = state

    def send_once(self, msg: Message) -> bytes:
        frames_to_send: List[tuple] = []
        use_bam = False

        with self.lock:
            if msg.is_diagnostic_dtc():
                state = self.get_dm1_state(msg.can_id)
                if state.spn_mode == "multi_dtc":
                    active_dtcs = [
                        DiagnosticTroubleCode(e.spn, e.fmi, e.oc)
                        for e in state.dtc_list
                        if e.active
                    ]
                    raw_frames = build_dm1_multi_dtc(
                        state.lamp_status,
                        active_dtcs,
                        state.flash_lamp_status,
                        msg.can_id_int(),
                    )
                    use_bam = len(active_dtcs) >= 2
                    dtc_desc = " | ".join(
                        f"SPN={d.spn} FMI={d.fmi} OC={d.occurrence_count}"
                        for d in active_dtcs
                    )
                    for i, (cid_int, frame_data) in enumerate(raw_frames):
                        cid_hex = f"{cid_int:08X}"
                        if i == 0 and use_bam:
                            dec = [DecodedSignal(
                                name="DM1-BAM",
                                raw=len(active_dtcs),
                                physical=float(len(active_dtcs)),
                                unit=dtc_desc or "no active DTCs",
                            )]
                        elif use_bam:
                            dec = [DecodedSignal(name=f"BAM-DT{i}", raw=i, physical=float(i), unit="")]
                        else:
                            dec_spn = active_dtcs[0].spn if active_dtcs else 0
                            dec_fmi = active_dtcs[0].fmi if active_dtcs else 0
                            dec_oc = active_dtcs[0].occurrence_count if active_dtcs else 0
                            dec = [DecodedSignal(
                                name="DM1",
                                raw=dec_spn,
                                physical=float(dec_spn),
                                unit=f"FMI={dec_fmi} OC={dec_oc}",
                            )]
                        frames_to_send.append((cid_int, cid_hex, frame_data, dec))
                else:
                    data = build_dm1_frame(
                        state.lamp_status,
                        state.spn,
                        state.fmi,
                        state.occurrence,
                        flash_lamp_status=state.flash_lamp_status,
                    )
                    decoded = [DecodedSignal(
                        name="DM1", raw=state.spn,
                        physical=float(state.spn),
                        unit=f"FMI={state.fmi} OC={state.occurrence}",
                    )]
                    frames_to_send.append((msg.can_id_int(), msg.can_id, data, decoded))
            else:
                data = build_frame(msg)
                decoded = [DecodedSignal(
                    name=s.name,
                    raw=clamp_raw(s.raw_value, s),
                    physical=clamp_raw(s.raw_value, s) * s.scale + s.offset,
                    unit=s.unit,
                ) for s in msg.signals]
                frames_to_send.append((msg.can_id_int(), msg.can_id, data, decoded))

        if not use_bam:
            cid_int, cid_hex, frame_data, dec = frames_to_send[0]
            self.pcan.request_send.emit(cid_int, frame_data)
            self.frame_sent.emit(time.time(), cid_hex, frame_data, dec, True)
        else:
            from PyQt5.QtCore import QTimer

            def _make_send(c, d, h, dc):
                def _do():
                    self.pcan.request_send.emit(c, d)
                    self.frame_sent.emit(time.time(), h, d, dc, True)
                return _do

            for i, (cid_int, cid_hex, frame_data, dec) in enumerate(frames_to_send):
                fn = _make_send(cid_int, frame_data, cid_hex, dec)
                if i == 0:
                    fn()
                else:
                    QTimer.singleShot(i * 50, fn)

        return frames_to_send[0][2]

