"""Sağ panel: seçili sinyalin tüm parametrelerinin düzenleme formu.

Min/Max alanları ham + fiziksel olarak ikili (paired) görünür ve canlı
çapraz güncellenir. Sine/Ramp parametreleri yalnızca ilgili sim_mode
seçildiğinde görünür.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRegExp, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QRegExpValidator
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
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
from gui.theme import repolish
from gui.waveform import WaveformWidget
from j1939_id import PgnCategory, parse_can_id


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


class _UnsignedIntegerEdit(QLineEdit):
    """Unsigned integer editor that is not limited by Qt's 32-bit QSpinBox."""

    valueChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = (1 << 64) - 1
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setValidator(QRegExpValidator(QRegExp(r"[0-9]{0,20}"), self))
        self.textEdited.connect(self._emit_if_valid)
        self.editingFinished.connect(self._normalize)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = int(minimum)
        self._maximum = int(maximum)

    def setValue(self, value: int) -> None:
        value = self._clamp(value)
        if self.text() != str(value):
            self.setText(str(value))

    def value(self) -> int:
        text = self.text().strip()
        if not text:
            return self._minimum
        return self._clamp(int(text))

    def _emit_if_valid(self, text: str) -> None:
        if not text:
            return
        self.valueChanged.emit(self.value())

    def _normalize(self) -> None:
        value = self.value()
        self.setText(str(value))
        self.valueChanged.emit(value)

    def _clamp(self, value: int) -> int:
        value = int(value)
        if value < self._minimum:
            return self._minimum
        if value > self._maximum:
            return self._maximum
        return value


class _RawPhysPair(QWidget):
    """Birbirini canlı güncelleyen ham + fiziksel alanı çifti."""

    changed = pyqtSignal(object, float)  # raw, physical

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.spin_raw = _UnsignedIntegerEdit()
        self.spin_raw.setRange(0, (1 << 64) - 1)
        _style_numeric_control(self.spin_raw)
        self.spin_phys = QDoubleSpinBox()
        self.spin_phys.setDecimals(4)
        self.spin_phys.setRange(-1e12, 1e12)
        _style_numeric_control(self.spin_phys, minimum_width=170)
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
        self.setMinimumWidth(500)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("SignalDetailContent")
        self.scroll.setWidget(content)

        outer = QVBoxLayout(content)
        outer.setContentsMargins(12, 10, 12, 14)
        outer.setSpacing(10)

        self.title = QLabel("Signal Detail")
        self.title.setObjectName("SignalDetailTitle")
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self.title.setFont(f)
        outer.addWidget(self.title)

        # --- J1939 ID summary ---
        self.grp_j1939 = QGroupBox("J1939 IDENTIFIER")
        f0 = QFormLayout(self.grp_j1939)
        _configure_form_layout(f0)
        self.lbl_j1939_pgn = QLabel("-")
        self.lbl_j1939_pgn_dec = QLabel("-")
        self.lbl_j1939_priority = QLabel("-")
        self.lbl_j1939_sa = QLabel("-")
        self.lbl_j1939_da_ge = QLabel("-")
        self.lbl_j1939_type = QLabel("-")
        for label in (
            self.lbl_j1939_pgn,
            self.lbl_j1939_pgn_dec,
            self.lbl_j1939_priority,
            self.lbl_j1939_sa,
            self.lbl_j1939_da_ge,
            self.lbl_j1939_type,
        ):
            _style_value_label(label)
        f0.addRow("PGN Hex:", self.lbl_j1939_pgn)
        f0.addRow("PGN Dec:", self.lbl_j1939_pgn_dec)
        f0.addRow("Priority:", self.lbl_j1939_priority)
        f0.addRow("Source Address:", self.lbl_j1939_sa)
        f0.addRow("DA / GE:", self.lbl_j1939_da_ge)
        f0.addRow("Type:", self.lbl_j1939_type)
        outer.addWidget(self.grp_j1939)

        # --- Identity ---
        self.grp_identity = QGroupBox("IDENTITY")
        f1 = QFormLayout(self.grp_identity)
        _configure_form_layout(f1)
        self.edt_name = QLineEdit()
        self.edt_unit = QLineEdit()
        for line_edit in (self.edt_name, self.edt_unit):
            line_edit.setMinimumHeight(32)
            line_edit.setMinimumWidth(260)
        self.edt_name.editingFinished.connect(self._on_text_changed)
        self.edt_unit.editingFinished.connect(self._on_text_changed)
        f1.addRow("Name:", self.edt_name)
        f1.addRow("Unit:", self.edt_unit)
        outer.addWidget(self.grp_identity)

        # --- Layout ---
        self.grp_layout = QGroupBox("BIT LAYOUT")
        f2 = QFormLayout(self.grp_layout)
        _configure_form_layout(f2)
        self.spin_byte = QSpinBox()
        self.spin_byte.setRange(0, 7)
        self.spin_bit = QSpinBox()
        self.spin_bit.setRange(0, 7)
        self.spin_len = QSpinBox()
        self.spin_len.setRange(1, 64)
        self.cmb_order = QComboBox()
        for k, label in BYTE_ORDERS:
            self.cmb_order.addItem(label, k)
        for spin in (self.spin_byte, self.spin_bit, self.spin_len):
            _style_numeric_control(spin)
        self.cmb_order.setMinimumHeight(32)
        self.cmb_order.setMinimumWidth(260)
        for w in (self.spin_byte, self.spin_bit, self.spin_len, self.cmb_order):
            if isinstance(w, QSpinBox):
                w.valueChanged.connect(self._on_value_changed)
            else:
                w.currentIndexChanged.connect(self._on_value_changed)
        f2.addRow("Byte Position (0-7):", self.spin_byte)
        f2.addRow("Bit Position (0-7):", self.spin_bit)
        f2.addRow("Bit Length (1-64):", self.spin_len)
        f2.addRow("Byte Order:", self.cmb_order)
        outer.addWidget(self.grp_layout)

        # --- Scale / Offset ---
        self.grp_scale = QGroupBox("SCALE / OFFSET")
        f3 = QFormLayout(self.grp_scale)
        _configure_form_layout(f3)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setDecimals(6)
        self.spin_scale.setRange(-1e9, 1e9)
        self.spin_scale.setValue(1.0)
        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setDecimals(6)
        self.spin_offset.setRange(-1e9, 1e9)
        for spin in (self.spin_scale, self.spin_offset):
            _style_numeric_control(spin)
        for w in (self.spin_scale, self.spin_offset):
            w.valueChanged.connect(self._on_scale_changed)
        f3.addRow("Scale:", self.spin_scale)
        f3.addRow("Offset:", self.spin_offset)
        self.lbl_scale_error = QLabel("Scale must not be zero.")
        self.lbl_scale_error.setObjectName("ScaleError")
        self.lbl_scale_error.setVisible(False)
        f3.addRow("", self.lbl_scale_error)
        outer.addWidget(self.grp_scale)

        # --- Range / Value (paired raw+phys) ---
        self.grp_range = QGroupBox("RANGE AND CURRENT VALUE")
        f4 = QFormLayout(self.grp_range)
        _configure_form_layout(f4)
        self.pair_min = _RawPhysPair()
        self.pair_max = _RawPhysPair()
        self.pair_value = _RawPhysPair()
        self.pair_min.changed.connect(self._on_value_changed)
        self.pair_max.changed.connect(self._on_value_changed)
        self.pair_value.changed.connect(self._on_value_changed)
        f4.addRow("Min:", self.pair_min)
        f4.addRow("Max:", self.pair_max)
        f4.addRow("Current:", self.pair_value)
        outer.addWidget(self.grp_range)

        # --- Simulation ---
        self.grp_simulation = QGroupBox("SIMULATION")
        f5 = QFormLayout(self.grp_simulation)
        _configure_form_layout(f5)
        self.cmb_mode = QComboBox()
        for k, label in SIM_MODES:
            self.cmb_mode.addItem(label, k)
        self.cmb_mode.setMinimumHeight(32)
        self.cmb_mode.setMinimumWidth(260)
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        f5.addRow("Mode:", self.cmb_mode)

        self.lbl_sine = QLabel("Sine Period (s):")
        self.spin_sine = QDoubleSpinBox()
        self.spin_sine.setDecimals(2)
        self.spin_sine.setRange(0.1, 3600.0)
        self.spin_sine.setValue(10.0)
        self.spin_sine.valueChanged.connect(self._on_value_changed)
        _style_numeric_control(self.spin_sine)
        f5.addRow(self.lbl_sine, self.spin_sine)

        # Sawtooth: ham/cycle adımı
        self.lbl_saw = QLabel("Sawtooth Step (raw/cycle):")
        self.spin_saw = QDoubleSpinBox()
        self.spin_saw.setDecimals(4)
        self.spin_saw.setRange(-1e9, 1e9)
        self.spin_saw.setSpecialValueText("auto")
        self.spin_saw.valueChanged.connect(self._on_value_changed)
        _style_numeric_control(self.spin_saw)
        f5.addRow(self.lbl_saw, self.spin_saw)

        # Ramp (üçgen dalga): periyot
        self.lbl_ramp = QLabel("Ramp Period (s):")
        self.spin_ramp = QDoubleSpinBox()
        self.spin_ramp.setDecimals(2)
        self.spin_ramp.setRange(0.1, 3600.0)
        self.spin_ramp.setValue(10.0)
        self.spin_ramp.valueChanged.connect(self._on_value_changed)
        _style_numeric_control(self.spin_ramp)
        f5.addRow(self.lbl_ramp, self.spin_ramp)
        outer.addWidget(self.grp_simulation)

        # --- Live preview ---
        self.grp_preview = QGroupBox("FRAME PREVIEW / WAVEFORM")
        pl = QVBoxLayout(self.grp_preview)
        pl.setSpacing(10)
        self.lbl_preview = QLabel("FF FF FF FF FF FF FF FF")
        self.lbl_preview.setObjectName("FrameBytes")
        self.lbl_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f6 = self.lbl_preview.font()
        f6.setFamily("JetBrains Mono")
        f6.setPointSize(max(11, f6.pointSize() + 2))
        f6.setBold(True)
        self.lbl_preview.setFont(f6)
        self.lbl_preview.setMinimumHeight(36)
        pl.addWidget(self.lbl_preview)
        self.waveform = WaveformWidget()
        pl.addWidget(self.waveform)
        outer.addWidget(self.grp_preview)

        outer.addStretch(1)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_signal(self, message: Optional[Message], signal: Optional[Signal]) -> None:
        self.message = message
        self.signal = signal
        self._refresh_j1939_summary()
        if signal is None:
            self.title.setText(
                "Diagnostic DTC message selected"
                if message and message.is_diagnostic_dtc()
                else "(no signal selected)"
            )
            self._set_signal_controls_enabled(False)
            self._clear_signal_fields()
            self._refresh_preview()
            self.waveform.set_signal(None)
            return
        self._set_signal_controls_enabled(True)
        self.title.setText(f"Signal: {signal.name}")
        self.waveform.set_signal(signal)
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
            self._update_scale_validation()

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
        self._update_scale_validation()
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

    def _update_scale_validation(self) -> None:
        invalid = self.spin_scale.value() == 0
        self.lbl_scale_error.setVisible(invalid)
        self.spin_scale.setProperty("invalid", invalid)
        repolish(self.spin_scale)
        if invalid:
            self.spin_scale.setToolTip("Scale must not be zero.")
        else:
            self.spin_scale.setToolTip("")

    def _set_signal_controls_enabled(self, enabled: bool) -> None:
        for group in (
            self.grp_identity,
            self.grp_layout,
            self.grp_scale,
            self.grp_range,
            self.grp_simulation,
            self.grp_preview,
        ):
            group.setEnabled(enabled)

    def _clear_signal_fields(self) -> None:
        self._loading = True
        try:
            self.edt_name.clear()
            self.edt_unit.clear()
            self.spin_byte.setValue(0)
            self.spin_bit.setValue(0)
            self.spin_len.setValue(1)
            self.cmb_order.setCurrentIndex(0)
            self.spin_scale.setValue(1.0)
            self.spin_offset.setValue(0.0)
            for pair in (self.pair_min, self.pair_max, self.pair_value):
                pair.set_scale_offset(1.0, 0.0)
                pair.set_raw(0)
            self.cmb_mode.setCurrentIndex(self.cmb_mode.findData("fixed"))
            self.spin_sine.setValue(10.0)
            self.spin_saw.setValue(self.spin_saw.minimum())
            self.spin_ramp.setValue(10.0)
            self._toggle_sim_extras("fixed")
            self._update_scale_validation()
        finally:
            self._loading = False

    def _refresh_j1939_summary(self) -> None:
        if self.message is None:
            self.lbl_j1939_pgn.setText("-")
            self.lbl_j1939_pgn_dec.setText("-")
            self.lbl_j1939_priority.setText("-")
            self.lbl_j1939_sa.setText("-")
            self.lbl_j1939_da_ge.setText("-")
            self.lbl_j1939_type.setText("-")
            return
        try:
            parsed = parse_can_id(self.message.can_id)
        except ValueError:
            self.lbl_j1939_pgn.setText("invalid")
            self.lbl_j1939_pgn_dec.setText("-")
            self.lbl_j1939_priority.setText("-")
            self.lbl_j1939_sa.setText("-")
            self.lbl_j1939_da_ge.setText("-")
            self.lbl_j1939_type.setText("invalid")
            return

        self.lbl_j1939_pgn.setText(f"{parsed.pgn:05X}")
        self.lbl_j1939_pgn_dec.setText(str(parsed.pgn))
        self.lbl_j1939_priority.setText(str(parsed.priority))
        self.lbl_j1939_sa.setText(f"{parsed.source_address:02X}")
        if parsed.destination_address is not None:
            self.lbl_j1939_da_ge.setText(f"DA {parsed.destination_address:02X}")
        else:
            self.lbl_j1939_da_ge.setText(f"GE {parsed.group_extension:02X}")
        self.lbl_j1939_type.setText(_category_label(parsed.category))

    def _refresh_preview(self) -> None:
        if self.message is None:
            self.lbl_preview.setText("FF FF FF FF FF FF FF FF")
            return
        try:
            data = build_frame(self.message)
            self.lbl_preview.setText(format_bytes(data))
            self.waveform.sample_now()
        except Exception:
            self.lbl_preview.setText("(error building frame)")


def _category_label(category: PgnCategory) -> str:
    return {
        PgnCategory.STANDARD: "standard",
        PgnCategory.REQUEST: "request",
        PgnCategory.TRANSPORT: "transport",
        PgnCategory.DIAGNOSTIC: "diagnostic",
        PgnCategory.PROPRIETARY_A: "proprietary A",
        PgnCategory.PROPRIETARY_B: "proprietary B",
        PgnCategory.UNKNOWN: "unknown",
    }[category]


def _configure_form_layout(layout: QFormLayout) -> None:
    layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    layout.setHorizontalSpacing(14)
    layout.setVerticalSpacing(8)


def _style_numeric_control(widget, minimum_width: int = 150) -> None:
    widget.setMinimumHeight(32)
    widget.setMinimumWidth(minimum_width)
    widget.setProperty("mono", "true")
    font = QFont("JetBrains Mono")
    font.setStyleHint(QFont.Monospace)
    font.setPointSize(max(11, font.pointSize()))
    widget.setFont(font)


def _style_value_label(label: QLabel) -> None:
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setObjectName("J1939Value")
    label.setMinimumWidth(190)
    label.setMinimumHeight(26)
    font = QFont("JetBrains Mono")
    font.setStyleHint(QFont.Monospace)
    font.setPointSize(max(11, font.pointSize()))
    label.setFont(font)
