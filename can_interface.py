"""PEAK PCAN-USB ile python-can üzerinden iletişim katmanı.

Tüm bus işlemleri (connect / disconnect / send) tek bir özel ``QThread`` üstünde
çalışır. UI tarafı yalnızca ``request_connect`` / ``request_disconnect`` /
``request_send`` sinyallerini emit eder; bus erişimi asla GUI thread'ini
bloklamaz.
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
    """python-can'in ``pcan`` arabirimine ince bir sarmalayıcı (QThread içinde)."""

    # --- Komut sinyalleri (UI -> bu nesne, queued) -----------------------
    request_connect = pyqtSignal()
    request_disconnect = pyqtSignal()
    request_send = pyqtSignal(int, bytes)
    request_shutdown = pyqtSignal()

    # --- Sonuç sinyalleri (bu nesne -> UI, queued) -----------------------
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
        self._bus = None  # PCAN thread tarafından okunur/yazılır
        self._last_error: str = ""

        # Thread oluştur, bu nesneyi oraya taşı, kendi sinyallerimizi
        # slotlarımıza otomatik queued connection ile bağla.
        self._thread = QThread()
        self._thread.setObjectName("PcanThread")
        self.moveToThread(self._thread)

        # Aynı QObject üzerinde sinyal -> slot bağlantısı, hedef thread
        # PcanThread olduğu için Qt otomatik queued connection kullanır.
        self.request_connect.connect(self._do_connect)
        self.request_disconnect.connect(self._do_disconnect)
        self.request_send.connect(self._do_send)
        self.request_shutdown.connect(self._do_shutdown)

    # ------------------------------------------------------------------
    # Lifecycle (main thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """PCAN thread'ini başlatır."""
        if not self._thread.isRunning():
            self._thread.start()

    def shutdown(self, wait_ms: int = 1500) -> None:
        """Bus'ı kapat ve thread'i sonlandır (main thread'den çağırılabilir)."""
        if self._thread.isRunning():
            self.request_shutdown.emit()
            self._thread.quit()
            self._thread.wait(wait_ms)

    # ------------------------------------------------------------------
    # Read-only durum (lock-free; race kabul edilebilir, sadece UI bilgi)
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._bus is not None

    @property
    def last_error(self) -> str:
        return self._last_error

    # ------------------------------------------------------------------
    # Slotlar (PCAN thread'inde çalışır)
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _do_connect(self) -> None:
        if self._bus is not None:
            self.connection_changed.emit(
                True, connection_info(self.backend, self.channel, self.bitrate)
            )
            return
        try:
            import can  # tembel import: paket yoksa UI yine de açılır

            self._bus = can.Bus(**build_bus_kwargs(self.backend, self.channel, self.bitrate))
            self._last_error = ""
            self.connection_changed.emit(
                True, connection_info(self.backend, self.channel, self.bitrate)
            )
        except Exception as exc:  # pragma: no cover - donanım/sürücü bağımlı
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
        except Exception as exc:  # pragma: no cover - donanım hatası
            self._last_error = str(exc)
            err_text = str(exc)
            # Bus muhtemelen kopmuş -> kapatıp UI'ya haber ver.
            try:
                bus.shutdown()
            except Exception:
                pass
            self._bus = None
            self.send_failed.emit(f"{can_id:08X}", err_text)
            self.connection_changed.emit(False, err_text)

    @pyqtSlot()
    def _do_shutdown(self) -> None:
        # Dahili kapanış: emit etmeden temiz kapat (uygulama kapanıyor).
        bus = self._bus
        self._bus = None
        if bus is not None:
            try:
                bus.shutdown()
            except Exception:
                pass
