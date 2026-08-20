"""DM1 (J1939-73) editor panel with simulation modes."""

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
from dm1_definitions import (
    get_lamp,
    lamp_sequence_label,
    load_dm1_definitions,
    set_lamp,
)
from frame_builder import build_dm1_frame, format_bytes
from simulator_engine import DM1State, SimulatorEngine


class DM1Panel(QWidget):
    def __init__(self, engine: SimulatorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.message: Optional[Message] = None
        self.dm1_definitions = load_dm1_definitions()
        self.lamp_checkboxes: dict[str, QCheckBox] = {}
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

        # Lamp Status
        lamp_group = QGroupBox("Lamp Status")
        lamp_main = QVBoxLayout(lamp_group)

        lamp_mode_row = QHBoxLayout()
        lamp_mode_row.addWidget(QLabel("Mode:"))
        self.cmb_lamp_mode = QComboBox()
        self.cmb_lamp_mode.addItems(["Fixed", "Auto (cycle)"])
        self.cmb_lamp_mode.currentIndexChanged.connect(self._on_lamp_mode_changed)
        lamp_mode_row.addWidget(self.cmb_lamp_mode)
        lamp_mode_row.addStretch()
        lamp_main.addLayout(lamp_mode_row)

        self.lamp_fixed_widget = QWidget()
        lamp_cb_layout = QHBoxLayout(self.lamp_fixed_widget)
        lamp_cb_layout.setContentsMargins(0, 0, 0, 0)
        for lamp in self.dm1_definitions.lamps:
            cb = QCheckBox(lamp.label)
            cb.toggled.connect(self._on_changed)
            lamp_cb_layout.addWidget(cb)
            self.lamp_checkboxes[lamp.key] = cb
        lamp_cb_layout.addStretch(1)
        lamp_main.addWidget(self.lamp_fixed_widget)

        self.lamp_auto_widget = QWidget()
        lamp_auto_layout = QHBoxLayout(self.lamp_auto_widget)
        lamp_auto_layout.setContentsMargins(0, 0, 0, 0)
        lamp_auto_layout.addWidget(QLabel("Cycle Period (s):"))
        self.spin_lamp_interval = QDoubleSpinBox()
        self.spin_lamp_interval.setRange(0.1, 60.0)
        self.spin_lamp_interval.setValue(2.0)
        self.spin_lamp_interval.setSingleStep(0.5)
        self.spin_lamp_interval.valueChanged.connect(self._on_changed)
        lamp_auto_layout.addWidget(self.spin_lamp_interval)
        lamp_auto_layout.addWidget(QLabel(lamp_sequence_label(self.dm1_definitions)))
        lamp_auto_layout.addStretch()
        self.lamp_auto_widget.setVisible(False)
        lamp_main.addWidget(self.lamp_auto_widget)

        layout.addWidget(lamp_group)

        # SPN Simulation Mode
        spn_group = QGroupBox("SPN Simulation")
        spn_main = QVBoxLayout(spn_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.cmb_spn_mode = QComboBox()
        self.cmb_spn_mode.addItems(["Fixed", "List (sequential)", "Random Range"])
        self.cmb_spn_mode.currentIndexChanged.connect(self._on_spn_mode_changed)
        mode_row.addWidget(self.cmb_spn_mode)
        mode_row.addStretch()
        spn_main.addLayout(mode_row)

        # Stacked: Fixed / List / Random
        self.spn_stack = QStackedWidget()

        # Fixed page
        fixed_page = QWidget()
        fixed_form = QFormLayout(fixed_page)
        self.spin_spn = QSpinBox()
        self.spin_spn.setRange(0, (1 << 19) - 1)
        self.spin_spn.valueChanged.connect(self._on_changed)
        fixed_form.addRow("SPN (0..524287):", self.spin_spn)
        self.spn_stack.addWidget(fixed_page)

        # List page
        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)

        list_ctrl_row = QHBoxLayout()
        self.spin_list_add = QSpinBox()
        self.spin_list_add.setRange(0, (1 << 19) - 1)
        self.spin_list_add.setFixedWidth(100)
        btn_list_add = QPushButton("Add")
        btn_list_add.clicked.connect(self._add_spn_to_list)
        btn_list_del = QPushButton("Delete")
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
        interval_row.addWidget(QLabel("Cycle Period (s):"))
        self.spin_list_interval = QDoubleSpinBox()
        self.spin_list_interval.setRange(0.1, 60.0)
        self.spin_list_interval.setValue(2.0)
        self.spin_list_interval.setSingleStep(0.5)
        self.spin_list_interval.valueChanged.connect(self._on_changed)
        interval_row.addWidget(self.spin_list_interval)
        interval_row.addStretch()
        list_layout.addLayout(interval_row)
        self.spn_stack.addWidget(list_page)

        # Random range page
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
        rand_form.addRow("Cycle Period (s):", self.spin_rand_interval)
        self.spn_stack.addWidget(rand_page)

        spn_main.addWidget(self.spn_stack)
        layout.addWidget(spn_group)

        # FMI / OC
        dtc_group = QGroupBox("DTC Detail")
        form = QFormLayout(dtc_group)

        self.cmb_fmi = QComboBox()
        for fmi in range(0, 32):
            desc = self.dm1_definitions.fmi_descriptions.get(fmi, "Reserved")
            self.cmb_fmi.addItem(f"{fmi} - {desc}", fmi)
        self.cmb_fmi.currentIndexChanged.connect(self._on_changed)
        form.addRow("FMI:", self.cmb_fmi)

        self.spin_oc = QSpinBox()
        self.spin_oc.setRange(0, 126)
        self.spin_oc.valueChanged.connect(self._on_changed)
        form.addRow("Occurrence Count (0..126):", self.spin_oc)
        layout.addWidget(dtc_group)

        # Preview / Send
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

            lamp_mode_idx = 1 if state.lamp_mode == "auto" else 0
            self.cmb_lamp_mode.setCurrentIndex(lamp_mode_idx)
            for key, checkbox in self.lamp_checkboxes.items():
                checkbox.setChecked(get_lamp(state.lamp_status, key, self.dm1_definitions))
            self.spin_lamp_interval.setValue(state.auto_lamp_interval_s)

            mode_map = {"fixed": 0, "list": 1, "random_range": 2}
            self.cmb_spn_mode.setCurrentIndex(mode_map.get(state.spn_mode, 0))
            self.spin_spn.setValue(state.spn)

            self.spn_list_widget.clear()
            for v in state.spn_list:
                self.spn_list_widget.addItem(str(v))
            self.spin_list_interval.setValue(state.spn_list_interval_s)

            self.spin_rand_min.setValue(state.spn_range_min)
            self.spin_rand_max.setValue(state.spn_range_max)
            self.spin_rand_interval.setValue(state.spn_range_interval_s)

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
        lamp = 0xFF
        lamp_mode = "auto" if self.cmb_lamp_mode.currentIndex() == 1 else "fixed"
        if lamp_mode == "fixed":
            for key, checkbox in self.lamp_checkboxes.items():
                lamp = set_lamp(lamp, key, checkbox.isChecked(), self.dm1_definitions)

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
