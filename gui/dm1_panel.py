"""DM1 (J1939-73) için özel düzenleme paneli - Simülasyon modları ile."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config_manager import Message
from frame_builder import build_dm1_frame, format_bytes
from simulator_engine import DM1State, SimulatorEngine

FMI_DESCRIPTIONS = {
    0: "Above normal / most severe",
    1: "Below normal / most severe",
    2: "Erratic, intermittent or incorrect",
    3: "Voltage above normal",
    4: "Voltage below normal",
    5: "Current below normal / open circuit",
    6: "Current above normal / grounded",
    7: "Mechanical system not responding",
    8: "Abnormal frequency / pulse width",
    9: "Abnormal update rate",
    10: "Abnormal rate of change",
    11: "Root cause unknown",
    12: "Bad intelligent device or component",
    13: "Out of calibration",
    14: "Special instructions",
    15: "Above normal / least severe",
    16: "Above normal / moderately severe",
    17: "Below normal / least severe",
    18: "Below normal / moderately severe",
    19: "Network error",
    20: "Data drifted high",
    21: "Data drifted low",
    31: "Condition exists",
}

LAMP_BITS = {"mil": 6, "red": 4, "amber": 2, "protect": 0}


def _set_lamp(byte_val: int, name: str, on: bool) -> int:
    shift = LAMP_BITS[name]
    mask = 0b11 << shift
    byte_val &= ~mask & 0xFF
    if on:
        byte_val |= (0b01 << shift) & 0xFF
    return byte_val


def _get_lamp(byte_val: int, name: str) -> bool:
    shift = LAMP_BITS[name]
    return ((byte_val >> shift) & 0b11) == 0b01


class DM1Panel(QWidget):
    def __init__(self, engine: SimulatorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.message: Optional[Message] = None
        self._loading = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.title = QLabel("DM1 - Active Diagnostic Trouble Codes")
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self.title.setFont(f)
        layout.addWidget(self.title)

        # ── Lamp Status ──────────────────────────────────────────────────
        lamp_group = QGroupBox("Lamp Status")
        lamp_main = QVBoxLayout(lamp_group)

        # Lamp modu seçimi
        lamp_mode_row = QHBoxLayout()
        lamp_mode_row.addWidget(QLabel("Mode:"))
        self.cmb_lamp_mode = QComboBox()
        self.cmb_lamp_mode.addItems(["Fixed", "Auto (döngüsel)"])
        self.cmb_lamp_mode.currentIndexChanged.connect(self._on_lamp_mode_changed)
        lamp_mode_row.addWidget(self.cmb_lamp_mode)
        lamp_mode_row.addStretch()
        lamp_main.addLayout(lamp_mode_row)

        # Fixed: checkbox'lar
        self.lamp_fixed_widget = QWidget()
        lamp_cb_layout = QHBoxLayout(self.lamp_fixed_widget)
        lamp_cb_layout.setContentsMargins(0, 0, 0, 0)
        self.cb_red = QCheckBox("Red Stop Lamp")
        self.cb_amber = QCheckBox("Amber Warning")
        self.cb_protect = QCheckBox("Protect Lamp")
        self.cb_mil = QCheckBox("MIL (Malfunction)")
        for cb in (self.cb_red, self.cb_amber, self.cb_protect, self.cb_mil):
            cb.toggled.connect(self._on_changed)
            lamp_cb_layout.addWidget(cb)
        lamp_cb_layout.addStretch(1)
        lamp_main.addWidget(self.lamp_fixed_widget)

        # Auto: interval
        self.lamp_auto_widget = QWidget()
        lamp_auto_layout = QHBoxLayout(self.lamp_auto_widget)
        lamp_auto_layout.setContentsMargins(0, 0, 0, 0)
        lamp_auto_layout.addWidget(QLabel("Değişim süresi (s):"))
        self.spin_lamp_interval = QDoubleSpinBox()
        self.spin_lamp_interval.setRange(0.1, 60.0)
        self.spin_lamp_interval.setValue(2.0)
        self.spin_lamp_interval.setSingleStep(0.5)
        self.spin_lamp_interval.valueChanged.connect(self._on_changed)
        lamp_auto_layout.addWidget(self.spin_lamp_interval)
        lamp_auto_layout.addWidget(QLabel("(Red → Amber → Protect → Hepsi döngüsü)"))
        lamp_auto_layout.addStretch()
        self.lamp_auto_widget.setVisible(False)
        lamp_main.addWidget(self.lamp_auto_widget)

        layout.addWidget(lamp_group)

        # ── SPN Simülasyon Modu ──────────────────────────────────────────
        spn_group = QGroupBox("SPN Simülasyon")
        spn_main = QVBoxLayout(spn_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mod:"))
        self.cmb_spn_mode = QComboBox()
        self.cmb_spn_mode.addItems(["Fixed", "Liste (sıralı)", "Random Aralık"])
        self.cmb_spn_mode.currentIndexChanged.connect(self._on_spn_mode_changed)
        mode_row.addWidget(self.cmb_spn_mode)
        mode_row.addStretch()
        spn_main.addLayout(mode_row)

        # Stacked: Fixed / List / Random
        self.spn_stack = QStackedWidget()

        # -- Fixed sayfası --
        fixed_page = QWidget()
        fixed_form = QFormLayout(fixed_page)
        self.spin_spn = QSpinBox()
        self.spin_spn.setRange(0, (1 << 19) - 1)
        self.spin_spn.valueChanged.connect(self._on_changed)
        fixed_form.addRow("SPN (0..524287):", self.spin_spn)
        self.spn_stack.addWidget(fixed_page)

        # -- Liste sayfası --
        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)

        list_ctrl_row = QHBoxLayout()
        self.spin_list_add = QSpinBox()
        self.spin_list_add.setRange(0, (1 << 19) - 1)
        self.spin_list_add.setFixedWidth(100)
        btn_list_add = QPushButton("Ekle")
        btn_list_add.clicked.connect(self._add_spn_to_list)
        btn_list_del = QPushButton("Sil")
        btn_list_del.clicked.connect(self._del_spn_from_list)
        list_ctrl_row.addWidget(QLabel("SPN:"))
        list_ctrl_row.addWidget(self.spin_list_add)
        list_ctrl_row.addWidget(btn_list_add)
        list_ctrl_row.addWidget(btn_list_del)
        list_ctrl_row.addStretch()
        list_layout.addLayout(list_ctrl_row)

        self.spn_list_widget = QListWidget()
        self.spn_list_widget.setMaximumHeight(100)
        list_layout.addWidget(self.spn_list_widget)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Değişim süresi (s):"))
        self.spin_list_interval = QDoubleSpinBox()
        self.spin_list_interval.setRange(0.1, 60.0)
        self.spin_list_interval.setValue(2.0)
        self.spin_list_interval.setSingleStep(0.5)
        self.spin_list_interval.valueChanged.connect(self._on_changed)
        interval_row.addWidget(self.spin_list_interval)
        interval_row.addStretch()
        list_layout.addLayout(interval_row)
        self.spn_stack.addWidget(list_page)

        # -- Random aralık sayfası --
        rand_page = QWidget()
        rand_form = QFormLayout(rand_page)
        self.spin_rand_min = QSpinBox()
        self.spin_rand_min.setRange(0, (1 << 19) - 1)
        self.spin_rand_min.valueChanged.connect(self._on_changed)
        self.spin_rand_max = QSpinBox()
        self.spin_rand_max.setRange(0, (1 << 19) - 1)
        self.spin_rand_max.setValue(1000)
        self.spin_rand_max.valueChanged.connect(self._on_changed)
        self.spin_rand_interval = QDoubleSpinBox()
        self.spin_rand_interval.setRange(0.1, 60.0)
        self.spin_rand_interval.setValue(2.0)
        self.spin_rand_interval.setSingleStep(0.5)
        self.spin_rand_interval.valueChanged.connect(self._on_changed)
        rand_form.addRow("Min SPN:", self.spin_rand_min)
        rand_form.addRow("Max SPN:", self.spin_rand_max)
        rand_form.addRow("Değişim süresi (s):", self.spin_rand_interval)
        self.spn_stack.addWidget(rand_page)

        spn_main.addWidget(self.spn_stack)
        layout.addWidget(spn_group)

        # ── FMI / OC ────────────────────────────────────────────────────
        dtc_group = QGroupBox("DTC Detay")
        form = QFormLayout(dtc_group)

        self.cmb_fmi = QComboBox()
        for fmi in range(0, 32):
            desc = FMI_DESCRIPTIONS.get(fmi, "Reserved")
            self.cmb_fmi.addItem(f"{fmi} - {desc}", fmi)
        self.cmb_fmi.currentIndexChanged.connect(self._on_changed)
        form.addRow("FMI:", self.cmb_fmi)

        self.spin_oc = QSpinBox()
        self.spin_oc.setRange(0, 126)
        self.spin_oc.valueChanged.connect(self._on_changed)
        form.addRow("Occurrence Count (0..126):", self.spin_oc)
        layout.addWidget(dtc_group)

        # ── Preview / Send ───────────────────────────────────────────────
        prev = QGroupBox("Frame Preview (8 bytes)")
        prev_l = QVBoxLayout(prev)
        self.lbl_preview = QLabel("FF FF FF FF FF FF FF FF")
        self.lbl_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f2 = self.lbl_preview.font()
        f2.setFamily("Consolas")
        f2.setPointSize(f2.pointSize() + 2)
        self.lbl_preview.setFont(f2)
        prev_l.addWidget(self.lbl_preview)
        layout.addWidget(prev)

        btns = QHBoxLayout()
        self.btn_send_once = QPushButton("Send Once")
        self.btn_send_once.clicked.connect(self._send_once)
        btns.addWidget(self.btn_send_once)
        btns.addStretch(1)
        layout.addLayout(btns)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def set_message(self, msg: Optional[Message]) -> None:
        self.message = msg
        self._loading = True
        try:
            if msg is None:
                self.title.setText("DM1")
                self._refresh_preview()
                return
            self.title.setText(f"{msg.can_id}  {msg.name}")
            state = self.engine.get_dm1_state(msg.can_id)

            # Lamp
            lamp_mode_idx = 1 if state.lamp_mode == "auto" else 0
            self.cmb_lamp_mode.setCurrentIndex(lamp_mode_idx)
            self.cb_red.setChecked(_get_lamp(state.lamp_status, "red"))
            self.cb_amber.setChecked(_get_lamp(state.lamp_status, "amber"))
            self.cb_protect.setChecked(_get_lamp(state.lamp_status, "protect"))
            self.cb_mil.setChecked(_get_lamp(state.lamp_status, "mil"))
            self.spin_lamp_interval.setValue(state.auto_lamp_interval_s)

            # SPN modu
            mode_map = {"fixed": 0, "list": 1, "random_range": 2}
            self.cmb_spn_mode.setCurrentIndex(mode_map.get(state.spn_mode, 0))
            self.spin_spn.setValue(state.spn)

            # Liste
            self.spn_list_widget.clear()
            for v in state.spn_list:
                self.spn_list_widget.addItem(str(v))
            self.spin_list_interval.setValue(state.spn_list_interval_s)

            # Random
            self.spin_rand_min.setValue(state.spn_range_min)
            self.spin_rand_max.setValue(state.spn_range_max)
            self.spin_rand_interval.setValue(state.spn_range_interval_s)

            # FMI / OC
            self.cmb_fmi.setCurrentIndex(self.cmb_fmi.findData(state.fmi))
            self.spin_oc.setValue(state.occurrence)
        finally:
            self._loading = False
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_lamp_mode_changed(self) -> None:
        is_auto = self.cmb_lamp_mode.currentIndex() == 1
        self.lamp_fixed_widget.setVisible(not is_auto)
        self.lamp_auto_widget.setVisible(is_auto)
        self._on_changed()

    def _on_spn_mode_changed(self) -> None:
        self.spn_stack.setCurrentIndex(self.cmb_spn_mode.currentIndex())
        self._on_changed()

    def _add_spn_to_list(self) -> None:
        val = self.spin_list_add.value()
        self.spn_list_widget.addItem(str(val))
        self._on_changed()

    def _del_spn_from_list(self) -> None:
        for item in self.spn_list_widget.selectedItems():
            self.spn_list_widget.takeItem(self.spn_list_widget.row(item))
        self._on_changed()

    def _current_state(self) -> DM1State:
        # Lamp
        lamp = 0xFF
        lamp_mode = "auto" if self.cmb_lamp_mode.currentIndex() == 1 else "fixed"
        if lamp_mode == "fixed":
            lamp = _set_lamp(lamp, "red", self.cb_red.isChecked())
            lamp = _set_lamp(lamp, "amber", self.cb_amber.isChecked())
            lamp = _set_lamp(lamp, "protect", self.cb_protect.isChecked())
            lamp = _set_lamp(lamp, "mil", self.cb_mil.isChecked())

        # SPN modu
        mode_idx = self.cmb_spn_mode.currentIndex()
        spn_mode = ["fixed", "list", "random_range"][mode_idx]

        spn_list = []
        for i in range(self.spn_list_widget.count()):
            try:
                spn_list.append(int(self.spn_list_widget.item(i).text()))
            except ValueError:
                pass

        state = DM1State(
            lamp_status=lamp,
            lamp_mode=lamp_mode,
            auto_lamp_interval_s=self.spin_lamp_interval.value(),
            spn=self.spin_spn.value(),
            spn_mode=spn_mode,
            spn_list=spn_list,
            spn_list_interval_s=self.spin_list_interval.value(),
            spn_range_min=self.spin_rand_min.value(),
            spn_range_max=self.spin_rand_max.value(),
            spn_range_interval_s=self.spin_rand_interval.value(),
            fmi=self.cmb_fmi.currentData() or 0,
            occurrence=self.spin_oc.value(),
        )
        return state

    def _on_changed(self) -> None:
        if self._loading or self.message is None:
            self._refresh_preview()
            return
        state = self._current_state()
        self.engine.set_dm1_state(self.message.can_id, state)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        state = self._current_state()
        data = build_dm1_frame(state.lamp_status, state.spn, state.fmi, state.occurrence)
        self.lbl_preview.setText(format_bytes(data))

    def _send_once(self) -> None:
        if self.message is None:
            return
        self.engine.send_once(self.message)