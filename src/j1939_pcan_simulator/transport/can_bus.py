"""CAN transport layer for PEAK PCAN-USB and python-can backends.

All bus operations run on a dedicated ``QThread``. The UI only emits
``request_connect``, ``request_disconnect``, and ``request_send`` signals, so
hardware access never blocks the GUI thread.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


DEFAULT_CHANNEL = "PCAN_USBBUS1"
DEFAULT_BITRATE = 250_000
DEFAULT_BACKEND = "pcan"
SUPPORTED_BACKENDS = ("pcan", "virtual")


def build_bus_kwargs(backend: str, channel: str, bitrate: int) -> dict:
    backend = normalize_backend(backend)
    if backend == "pcan":
        return {
            "interface": "pcan",
            "channel": channel,
            "bitrate": bitrate,
        }
    if backend == "virtual":
        return {
            "interface": "virtual",
            "channel": channel or "j1939-simulator",
            "receive_own_messages": False,
        }
    raise ValueError(f"Unsupported CAN backend: {backend}")


def normalize_backend(backend: str) -> str:
    backend = (backend or DEFAULT_BACKEND).strip().lower()
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unsupported CAN backend: {backend}")
    return backend


def connection_info(backend: str, channel: str, bitrate: int) -> str:
    backend = normalize_backend(backend)
    if backend == "virtual":
        return f"virtual:{channel or 'j1939-simulator'}"
    return f"{channel} @ {bitrate} bit/s"


class PCanInterface(QObject):
    """Thin QThread-backed wrapper around python-can bus interfaces."""

    # Command signals: UI -> this object, queued.
    request_connect = pyqtSignal()
    request_disconnect = pyqtSignal()
    request_send = pyqtSignal(int, bytes)
    request_shutdown = pyqtSignal()

    # Result signals: this object -> UI, queued.
    # (connected: bool, info_or_error: str)
    connection_changed = pyqtSignal(bool, str)
    # (can_id_hex_8char, error_text)
    send_failed = pyqtSignal(str, str)

    def __init__(
        self,
        backend: str = DEFAULT_BACKEND,
        channel: str = DEFAULT_CHANNEL,
        bitrate: int = DEFAULT_BITRATE,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.backend = normalize_backend(backend)
        self.channel = channel
        self.bitrate = bitrate
        self._bus = None  # Read and written only by the CAN worker thread.
        self._last_error: str = ""

        self._thread = QThread()
        self._thread.setObjectName("PcanThread")
        self.moveToThread(self._thread)

        # Signal/slot connections target this object's worker thread.
        self.request_connect.connect(self._do_connect)
        self.request_disconnect.connect(self._do_disconnect)
        self.request_send.connect(self._do_send)
        self.request_shutdown.connect(self._do_shutdown)

    # ------------------------------------------------------------------
    # Lifecycle (main thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the CAN worker thread."""
        if not self._thread.isRunning():
            self._thread.start()

    def shutdown(self, wait_ms: int = 1500) -> None:
        """Close the bus and stop the worker thread from the main thread."""
        if self._thread.isRunning():
            self.request_shutdown.emit()
            self._thread.quit()
            self._thread.wait(wait_ms)

    # ------------------------------------------------------------------
    # Read-only state. Lock-free is acceptable because this is UI-only status.
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._bus is not None

    @property
    def last_error(self) -> str:
        return self._last_error

    # ------------------------------------------------------------------
    # Slots running on the CAN worker thread.
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _do_connect(self) -> None:
        if self._bus is not None:
            self.connection_changed.emit(
                True, connection_info(self.backend, self.channel, self.bitrate)
            )
            return
        try:
            import can  # Lazy import: the UI can still open if python-can fails.

            self._bus = can.Bus(**build_bus_kwargs(self.backend, self.channel, self.bitrate))
            self._last_error = ""
            self.connection_changed.emit(
                True, connection_info(self.backend, self.channel, self.bitrate)
            )
        except Exception as exc:  # pragma: no cover - hardware/driver dependent
            self._bus = None
            self._last_error = (
                f"{self.backend} backend failed for {self.channel}: {exc}"
            )
            self.connection_changed.emit(False, self._last_error)

    @pyqtSlot()
    def _do_disconnect(self) -> None:
        bus = self._bus
        self._bus = None
        if bus is not None:
            try:
                bus.shutdown()
            except Exception:
                pass
            self.connection_changed.emit(False, "Disconnected")

    @pyqtSlot(int, bytes)
    def _do_send(self, can_id: int, data: bytes) -> None:
        bus = self._bus
        if bus is None:
            return
        try:
            import can  # type: ignore

            msg = can.Message(
                arbitration_id=can_id,
                is_extended_id=True,
                data=bytes(data),
            )
            bus.send(msg)
        except Exception as exc:  # pragma: no cover - hardware failure
            self._last_error = str(exc)
            err_text = str(exc)
            # The bus is probably gone; close it and notify the UI.
            try:
                bus.shutdown()
            except Exception:
                pass
            self._bus = None
            self.send_failed.emit(f"{can_id:08X}", err_text)
            self.connection_changed.emit(False, err_text)

    @pyqtSlot()
    def _do_shutdown(self) -> None:
        # Internal shutdown: close quietly while the application is exiting.
        bus = self._bus
        self._bus = None
        if bus is not None:
            try:
                bus.shutdown()
            except Exception:
                pass

