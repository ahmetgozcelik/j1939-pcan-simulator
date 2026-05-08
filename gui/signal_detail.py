"""Sağ panel: seçili sinyalin tüm parametrelerinin düzenleme formu.

Min/Max alanları ham + fiziksel olarak ikili (paired) görünür ve canlı
çapraz güncellenir. Sine/Ramp parametreleri yalnızca ilgili sim_mode
seçildiğinde görünür.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config_manager import Message, Signal
from frame_builder import (
    build_frame,
    format_bytes,
    physical_to_raw,
    raw_to_physical,
)


SIM_MODES = [
    ("fixed", "Fixed"),
    ("random", "Random"),
    ("sine", "Sine"),
    ("sawtooth", "Sawtooth"),
    ("ramp", "Ramp (triangle)"),
]

BYTE_ORDERS = [
    ("little_endian", "Little Endian (Intel)"),
    ("big_endian", "Big Endian (Motorola)"),
]


class _RawPhysPair(QWidget):
    """Birbirini canlı güncelleyen ham + fiziksel alanı çifti."""

    changed = pyqtSignal(int, float)  # raw, physical

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.spin_raw = QSpinBox()
        self.spin_raw.setRange(0, (1 << 31) - 1)
        self.spin_raw.setMinimumWidth(110)
        self.spin_phys = QDoubleSpinBox()
        self.spin_phys.setDecimals(4)
        self.spin_phys.setRange(-1e12, 1e12)
        self.spin_phys.setMinimumWidth(140)
        layout.addWidget(QLabel("raw"))
        layout.addWidget(self.spin_raw, 1)
        layout.addWidget(QLabel("phys"))
        layout.addWidget(self.spin_phys, 1)

        self._scale = 1.0
        self._offset = 0.0
        self._suppress = False

        self.spin_raw.valueChanged.connect(self._on_raw)
        self.spin_phys.valueChanged.connect(self._on_phys)

    def set_scale_offset(self, scale: float, offset: float) -> None:
        self._scale = scale
        self._offset = offset
        # Mevcut ham değeri fiziksel'e yansıt.
        self._suppress = True
        try:
            self.spin_phys.setValue(raw_to_physical(self.spin_raw.value(), scale, offset))
        finally:
            self._suppress = False

    def set_raw(self, value: int) -> None:
        self._suppress = True
        try:
            self.spin_raw.setValue(value)
            self.spin_phys.setValue(raw_to_physical(value, self._scale, self._offset))
        finally:
            self._suppress = False

    def raw(self) -> int:
        return int(self.spin_raw.value())

    def _on_raw(self, raw: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.spin_phys.setValue(raw_to_physical(raw, self._scale, self._offset))
        finally:
            self._suppress = False
        self.changed.emit(raw, self.spin_phys.value())

    def _on_phys(self, phys: float) -> None:
        if self._suppress:
            return
        raw = physical_to_raw(phys, self._scale, self._offset)
        self._suppress = True
        try:
            self.spin_raw.setValue(raw)
        finally:
            self._suppress = False
        self.changed.emit(raw, phys)


class SignalDetail(QWidget):

    # Sinyal verisi düzenlendiğinde haber verir.
    signal_modified = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.message: Optional[Message] = None
        self.signal: Optional[Signal] = None
        self._loading = False
        self._build_ui()
        self._toggle_sim_extras("fixed")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self.title = QLabel("Signal Detail")
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self.title.setFont(f)
        outer.addWidget(self.title)

        # --- Identity ---
        ident = QGroupBox("Identity")
        f1 = QFormLayout(ident)
        self.edt_name = QLineEdit()
        self.edt_unit = QLineEdit()
        self.edt_name.editingFinished.connect(self._on_text_changed)
        self.edt_unit.editingFinished.connect(self._on_text_changed)
        f1.addRow("Name:", self.edt_name)
        f1.addRow("Unit:", self.edt_unit)
        outer.addWidget(ident)

        # --- Layout ---
        lay = QGroupBox("Bit Layout")
        f2 = QFormLayout(lay)
        self.spin_byte = QSpinBox()
        self.spin_byte.setRange(0, 7)
        self.spin_bit = QSpinBox()
        self.spin_bit.setRange(0, 7)
        self.spin_len = QSpinBox()
        self.spin_len.setRange(1, 64)
        self.cmb_order = QComboBox()
        for k, label in BYTE_ORDERS:
            self.cmb_order.addItem(label, k)
        for w in (self.spin_byte, self.spin_bit, self.spin_len, self.cmb_order):
            if isinstance(w, QSpinBox):
                w.valueChanged.connect(self._on_value_changed)
            else:
                w.currentIndexChanged.connect(self._on_value_changed)
        f2.addRow("Byte Position (0-7):", self.spin_byte)
        f2.addRow("Bit Position (0-7):", self.spin_bit)
        f2.addRow("Bit Length (1-64):", self.spin_len)
        f2.addRow("Byte Order:", self.cmb_order)
        outer.addWidget(lay)

        # --- Scale / Offset ---
        sc = QGroupBox("Scale / Offset")
        f3 = QFormLayout(sc)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setDecimals(6)
        self.spin_scale.setRange(-1e9, 1e9)
        self.spin_scale.setValue(1.0)
        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setDecimals(6)
        self.spin_offset.setRange(-1e9, 1e9)
        for w in (self.spin_scale, self.spin_offset):
            w.valueChanged.connect(self._on_scale_changed)
        f3.addRow("Scale:", self.spin_scale)
        f3.addRow("Offset:", self.spin_offset)
        outer.addWidget(sc)

        # --- Range / Value (paired raw+phys) ---
        rng = QGroupBox("Range and Current Value")
        f4 = QFormLayout(rng)
        self.pair_min = _RawPhysPair()
        self.pair_max = _RawPhysPair()
        self.pair_value = _RawPhysPair()
        self.pair_min.changed.connect(self._on_value_changed)
        self.pair_max.changed.connect(self._on_value_changed)
        self.pair_value.changed.connect(self._on_value_changed)
        f4.addRow("Min:", self.pair_min)
        f4.addRow("Max:", self.pair_max)
        f4.addRow("Current:", self.pair_value)
        outer.addWidget(rng)

        # --- Simulation ---
        sim = QGroupBox("Simulation")
        f5 = QFormLayout(sim)
        self.cmb_mode = QComboBox()
        for k, label in SIM_MODES:
            self.cmb_mode.addItem(label, k)
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        f5.addRow("Mode:", self.cmb_mode)

        self.lbl_sine = QLabel("Sine Period (s):")
        self.spin_sine = QDoubleSpinBox()
        self.spin_sine.setDecimals(2)
        self.spin_sine.setRange(0.1, 3600.0)
        self.spin_sine.setValue(10.0)
        self.spin_sine.valueChanged.connect(self._on_value_changed)
        f5.addRow(self.lbl_sine, self.spin_sine)

        # Sawtooth: ham/cycle adımı
        self.lbl_saw = QLabel("Sawtooth Step (raw/cycle):")
        self.spin_saw = QDoubleSpinBox()
        self.spin_saw.setDecimals(4)
        self.spin_saw.setRange(-1e9, 1e9)
        self.spin_saw.setSpecialValueText("auto")
        self.spin_saw.valueChanged.connect(self._on_value_changed)
        f5.addRow(self.lbl_saw, self.spin_saw)

        # Ramp (üçgen dalga): periyot
        self.lbl_ramp = QLabel("Ramp Period (s):")
        self.spin_ramp = QDoubleSpinBox()
        self.spin_ramp.setDecimals(2)
        self.spin_ramp.setRange(0.1, 3600.0)
        self.spin_ramp.setValue(10.0)
        self.spin_ramp.valueChanged.connect(self._on_value_changed)
        f5.addRow(self.lbl_ramp, self.spin_ramp)
        outer.addWidget(sim)

        # --- Live preview ---
        prev = QGroupBox("Frame Preview (whole message)")
        pl = QVBoxLayout(prev)
        self.lbl_preview = QLabel("FF FF FF FF FF FF FF FF")
        self.lbl_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f6 = self.lbl_preview.font()
        f6.setFamily("Consolas")
        f6.setPointSize(f6.pointSize() + 2)
        self.lbl_preview.setFont(f6)
        pl.addWidget(self.lbl_preview)
        outer.addWidget(prev)

        outer.addStretch(1)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_signal(self, message: Optional[Message], signal: Optional[Signal]) -> None:
        self.message = message
        self.signal = signal
        if signal is None:
            self.title.setText("(no signal selected)")
            self.setEnabled(False)
            self._refresh_preview()
            return
        self.setEnabled(True)
        self.title.setText(f"Signal: {signal.name}")
        self._loading = True
        try:
            self.edt_name.setText(signal.name)
            self.edt_unit.setText(signal.unit)
            self.spin_byte.setValue(signal.byte_pos)
            self.spin_bit.setValue(signal.bit_pos)
            self.spin_len.setValue(signal.bit_length)
            idx = self.cmb_order.findData(signal.byte_order)
            self.cmb_order.setCurrentIndex(idx if idx >= 0 else 0)
            self.spin_scale.setValue(signal.scale)
            self.spin_offset.setValue(signal.offset)

            # Çiftlere scale/offset uygula sonra değerleri yükle.
            for pair in (self.pair_min, self.pair_max, self.pair_value):
                pair.set_scale_offset(signal.scale, signal.offset)
            self.pair_min.set_raw(signal.raw_min)
            self.pair_max.set_raw(signal.raw_max)
            self.pair_value.set_raw(signal.raw_value)

            mode_idx = self.cmb_mode.findData(signal.sim_mode)
            self.cmb_mode.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
            self.spin_sine.setValue(signal.sine_period_s or 10.0)
            self.spin_saw.setValue(
                signal.ramp_step if signal.ramp_step is not None else self.spin_saw.minimum()
            )
            self.spin_ramp.setValue(signal.ramp_period_s or 10.0)
            self._toggle_sim_extras(signal.sim_mode)
        finally:
            self._loading = False
        self._refresh_preview()

    def refresh_after_external_edit(self) -> None:
        """Sinyal harici (örn. signal_panel inline edit) güncellenmişse formu tazeler."""
        self.set_signal(self.message, self.signal)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        if self._loading or self.signal is None:
            return
        self.signal.name = self.edt_name.text() or "Signal"
        self.signal.unit = self.edt_unit.text()
        self.title.setText(f"Signal: {self.signal.name}")
        self.signal_modified.emit()
        self._refresh_preview()

    def _on_value_changed(self, *_args) -> None:
        if self._loading or self.signal is None:
            return
        s = self.signal
        s.byte_pos = self.spin_byte.value()
        s.bit_pos = self.spin_bit.value()
        s.bit_length = self.spin_len.value()
        s.byte_order = self.cmb_order.currentData()
        s.raw_min = self.pair_min.raw()
        s.raw_max = self.pair_max.raw()
        s.raw_value = self.pair_value.raw()
        s.sim_mode = self.cmb_mode.currentData()
        s.sine_period_s = self.spin_sine.value()
        # Sawtooth step "auto" özel değeri minimum'da; minimum -1e9 olduğundan
        # yalnızca tam minimum'da auto kabul edelim.
        if self.spin_saw.value() == self.spin_saw.minimum():
            s.ramp_step = None
        else:
            s.ramp_step = self.spin_saw.value()
        s.ramp_period_s = self.spin_ramp.value()
        self.signal_modified.emit()
        self._refresh_preview()

    def _on_scale_changed(self, *_args) -> None:
        if self._loading or self.signal is None:
            return
        scale = self.spin_scale.value()
        offset = self.spin_offset.value()
        self.signal.scale = scale
        self.signal.offset = offset
        for pair in (self.pair_min, self.pair_max, self.pair_value):
            pair.set_scale_offset(scale, offset)
        self.signal_modified.emit()
        self._refresh_preview()

    def _on_mode_changed(self, *_args) -> None:
        mode = self.cmb_mode.currentData() or "fixed"
        self._toggle_sim_extras(mode)
        self._on_value_changed()

    def _toggle_sim_extras(self, mode: str) -> None:
        sine_visible = mode == "sine"
        saw_visible = mode == "sawtooth"
        ramp_visible = mode == "ramp"
        for w in (self.lbl_sine, self.spin_sine):
            w.setVisible(sine_visible)
        for w in (self.lbl_saw, self.spin_saw):
            w.setVisible(saw_visible)
        for w in (self.lbl_ramp, self.spin_ramp):
            w.setVisible(ramp_visible)

    def _refresh_preview(self) -> None:
        if self.message is None:
            self.lbl_preview.setText("FF FF FF FF FF FF FF FF")
            return
        try:
            data = build_frame(self.message)
            self.lbl_preview.setText(format_bytes(data))
        except Exception:
            self.lbl_preview.setText("(error building frame)")
