"""DM1 (J1939-73) editor panel with simulation modes."""

from __future__ import annotations

import sys
from typing import Optional

from PyQt5.QtCore import QProcess, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config_manager import Message
from dm1_definitions import (
    CONFIG_PATH,
    get_lamp,
    load_dm1_definitions,
    set_lamp,
)
from frame_builder import build_dm1_frame, format_bytes
from simulator_engine import DM1State, SimulatorEngine

DEFINITION_DISPLAY_PATH = "configs/dm1_definitions.json"


class DM1Panel(QWidget):
    def __init__(self, engine: SimulatorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.message: Optional[Message] = None
        self.dm1_definitions = load_dm1_definitions()
        self.lamp_checkboxes: dict[str, QAbstractButton] = {}
        self.flash_lamp_checkboxes: dict[str, QAbstractButton] = {}
        self.lamp_matrix_layout: Optional[QGridLayout] = None
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
        self.title.setObjectName("PanelTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.title)

        # Lamp Status
        lamp_group = QGroupBox("Lamp Status")
        lamp_main = QVBoxLayout(lamp_group)

        lamp_mode_row = QHBoxLayout()
        lamp_mode_row.addWidget(QLabel("Mode:"))
        self.cmb_lamp_mode = QComboBox()
        self.cmb_lamp_mode.addItems(["Fixed", "Auto (cycle)"])
        self.cmb_lamp_mode.setFixedWidth(140)
        self.cmb_lamp_mode.currentIndexChanged.connect(self._on_lamp_mode_changed)
        lamp_mode_row.addWidget(self.cmb_lamp_mode)
        lamp_mode_row.addStretch()
        self.btn_open_definitions = QPushButton("Edit JSON...")
        self.btn_open_definitions.setFixedWidth(112)
        self.btn_open_definitions.setToolTip(f"Open {DEFINITION_DISPLAY_PATH}")
        self.btn_open_definitions.clicked.connect(self._open_definitions)
        self.btn_reload_definitions = QPushButton("Reload JSON")
        self.btn_reload_definitions.setFixedWidth(112)
        self.btn_reload_definitions.setToolTip("Reload DM1 definitions after editing the JSON file")
        self.btn_reload_definitions.clicked.connect(self._reload_definitions)
        lamp_mode_row.addWidget(self.btn_open_definitions)
        lamp_mode_row.addWidget(self.btn_reload_definitions)
        lamp_main.addLayout(lamp_mode_row)

        self.lbl_definitions_status = QLabel(f"Definition file: {DEFINITION_DISPLAY_PATH}")
        self.lbl_definitions_status.setObjectName("SecondaryText")
        self.lbl_definitions_status.setWordWrap(True)
        self.lbl_definitions_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lamp_main.addWidget(self.lbl_definitions_status)

        self.lbl_lamp_mode_hint = QLabel("Status lamps are manual in Fixed mode. Flash lamps remain manual.")
        self.lbl_lamp_mode_hint.setObjectName("SecondaryText")
        self.lbl_lamp_mode_hint.setWordWrap(True)
        lamp_main.addWidget(self.lbl_lamp_mode_hint)

        self.lamp_matrix_widget = QWidget()
        self.lamp_matrix_widget.setObjectName("LampMatrix")
        self.lamp_matrix_layout = QGridLayout(self.lamp_matrix_widget)
        self.lamp_matrix_layout.setContentsMargins(0, 0, 0, 0)
        self.lamp_matrix_layout.setHorizontalSpacing(8)
        self.lamp_matrix_layout.setVerticalSpacing(6)
        self._populate_lamp_matrix()
        lamp_main.addWidget(self.lamp_matrix_widget)

        self.lamp_auto_widget = QWidget()
        lamp_auto_layout = QHBoxLayout(self.lamp_auto_widget)
        lamp_auto_layout.setContentsMargins(0, 0, 0, 0)
        lbl_cycle_period = QLabel("Cycle Period (s):")
        lbl_cycle_period.setFixedWidth(112)
        lamp_auto_layout.addWidget(lbl_cycle_period)
        self.spin_lamp_interval = QDoubleSpinBox()
        self.spin_lamp_interval.setRange(0.1, 60.0)
        self.spin_lamp_interval.setValue(2.0)
        self.spin_lamp_interval.setFixedWidth(96)
        self.spin_lamp_interval.setSingleStep(0.5)
        self.spin_lamp_interval.valueChanged.connect(self._on_changed)
        lamp_auto_layout.addWidget(self.spin_lamp_interval)
        self.lbl_lamp_sequence = QLabel(self._lamp_cycle_text())
        self.lbl_lamp_sequence.setObjectName("SecondaryText")
        self.lbl_lamp_sequence.setWordWrap(True)
        self.lbl_lamp_sequence.setMaximumWidth(220)
        lamp_auto_layout.addWidget(self.lbl_lamp_sequence, 1)
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
        dtc_layout = QGridLayout(dtc_group)
        dtc_layout.setHorizontalSpacing(10)
        dtc_layout.setVerticalSpacing(8)

        self.cmb_fmi = QComboBox()
        self.cmb_fmi.setMinimumContentsLength(16)
        self.cmb_fmi.setFixedWidth(320)
        self.cmb_fmi.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._populate_fmi_combo()
        self.cmb_fmi.currentIndexChanged.connect(self._on_changed)
        lbl_fmi = QLabel("FMI:")
        lbl_fmi.setFixedWidth(132)
        dtc_layout.addWidget(lbl_fmi, 0, 0)
        dtc_layout.addWidget(self.cmb_fmi, 0, 1)

        lbl_occurrence = QLabel("Occurrence Count:")
        lbl_occurrence.setFixedWidth(132)
        lbl_occurrence.setToolTip("J1939 DTC occurrence count range: 0..126")
        self.spin_oc = QSpinBox()
        self.spin_oc.setRange(0, 126)
        self.spin_oc.valueChanged.connect(self._on_changed)
        self.spin_oc.setFixedWidth(96)
        dtc_layout.addWidget(lbl_occurrence, 1, 0)
        dtc_layout.addWidget(self.spin_oc, 1, 1)
        dtc_layout.setColumnStretch(1, 1)
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
                self.title.setToolTip("")
                self._refresh_preview()
                return
            self.title.setText(f"{msg.can_id}  {msg.name}")
            self.title.setToolTip(f"{msg.can_id}  {msg.name}")
            state = self.engine.get_dm1_state(msg.can_id)

            lamp_mode_idx = 1 if state.lamp_mode == "auto" else 0
            self.cmb_lamp_mode.setCurrentIndex(lamp_mode_idx)
            self._sync_lamp_mode_enabled()
            for key, checkbox in self.lamp_checkboxes.items():
                checkbox.setChecked(get_lamp(state.lamp_status, key, self.dm1_definitions))
            for key, checkbox in self.flash_lamp_checkboxes.items():
                checkbox.setChecked(get_lamp(state.flash_lamp_status, key, self.dm1_definitions))
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

    def _populate_lamp_matrix(self) -> None:
        layout = self.lamp_matrix_layout
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.lamp_checkboxes.clear()
        self.flash_lamp_checkboxes.clear()

        for column, text in enumerate(("Lamp", "Status", "Flash")):
            header = QLabel(text)
            header.setObjectName("LampMatrixHeader")
            layout.addWidget(header, 0, column)

        for row, lamp in enumerate(self.dm1_definitions.lamps, start=1):
            display_label = self._lamp_display_label(lamp.key, lamp.label)
            name = QLabel(display_label)
            name.setObjectName("LampMatrixLabel")
            name.setToolTip(f"{lamp.label} - DM1/DM2 bits {lamp.bit}..{lamp.bit + 1}")
            name.setMinimumWidth(112)
            layout.addWidget(name, row, 0)

            status_btn = self._create_lamp_button(lamp.label, lamp.bit, flash=False)
            flash_btn = self._create_lamp_button(lamp.label, lamp.bit, flash=True)
            layout.addWidget(status_btn, row, 1)
            layout.addWidget(flash_btn, row, 2)
            self.lamp_checkboxes[lamp.key] = status_btn
            self.flash_lamp_checkboxes[lamp.key] = flash_btn

        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 2)

    def _lamp_display_label(self, key: str, label: str) -> str:
        return {
            "red": "Red Stop",
            "amber": "Amber Warn",
            "protect": "Protect",
            "mil": "MIL",
        }.get(key, label)

    def _lamp_cycle_text(self) -> str:
        return "Cycle: Red -> Amber -> Protect -> All"

    def _create_lamp_button(self, label: str, bit: int, *, flash: bool) -> QToolButton:
        button = QToolButton()
        button.setObjectName("LampStatusTile")
        button.setCheckable(True)
        button.setMinimumHeight(34)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        kind = "Flash" if flash else "Status"
        button.setToolTip(f"{label} - {kind} bits {bit}..{bit + 1}")
        button.toggled.connect(lambda checked, btn=button: self._update_lamp_button(btn, checked))
        button.toggled.connect(self._on_changed)
        self._update_lamp_button(button, False)
        return button

    def _update_lamp_button(self, button: QAbstractButton, checked: bool) -> None:
        button.setProperty("active", checked)
        button.setText("ON" if checked else "OFF")
        button.style().unpolish(button)
        button.style().polish(button)

    def _populate_fmi_combo(self) -> None:
        current = self.cmb_fmi.currentData() if hasattr(self, "cmb_fmi") else 0
        self.cmb_fmi.blockSignals(True)
        self.cmb_fmi.clear()
        for fmi in range(0, 32):
            desc = self.dm1_definitions.fmi_descriptions.get(fmi, "Reserved")
            self.cmb_fmi.addItem(f"{fmi} - {desc}", fmi)
            self.cmb_fmi.setItemData(self.cmb_fmi.count() - 1, desc, Qt.ToolTipRole)
        idx = self.cmb_fmi.findData(current)
        self.cmb_fmi.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_fmi.blockSignals(False)

    def _open_definitions(self) -> None:
        opened = False
        if sys.platform.startswith("win"):
            opened = QProcess.startDetached("notepad.exe", [str(CONFIG_PATH)])
        if not opened:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_PATH)))
        if opened:
            self.lbl_definitions_status.setText(f"Opened definition file: {DEFINITION_DISPLAY_PATH}")
        else:
            self.lbl_definitions_status.setText(f"Could not open definition file: {DEFINITION_DISPLAY_PATH}")

    def _reload_definitions(self) -> None:
        state = self._current_state()
        self.dm1_definitions = load_dm1_definitions()
        self._populate_lamp_matrix()
        self.lbl_lamp_sequence.setText(self._lamp_cycle_text())
        self._sync_lamp_mode_enabled()
        self._populate_fmi_combo()
        for key, checkbox in self.lamp_checkboxes.items():
            try:
                checkbox.setChecked(get_lamp(state.lamp_status, key, self.dm1_definitions))
            except KeyError:
                checkbox.setChecked(False)
        for key, checkbox in self.flash_lamp_checkboxes.items():
            try:
                checkbox.setChecked(get_lamp(state.flash_lamp_status, key, self.dm1_definitions))
            except KeyError:
                checkbox.setChecked(False)
        self.lbl_definitions_status.setText(
            f"Reloaded {len(self.dm1_definitions.lamps)} lamp definitions and "
            f"{len(self.dm1_definitions.fmi_descriptions)} FMI descriptions."
        )
        self._on_changed()

    def _on_lamp_mode_changed(self) -> None:
        is_auto = self.cmb_lamp_mode.currentIndex() == 1
        self._sync_lamp_mode_enabled()
        self.lamp_auto_widget.setVisible(is_auto)
        self._on_changed()

    def _sync_lamp_mode_enabled(self) -> None:
        is_auto = self.cmb_lamp_mode.currentIndex() == 1
        for button in self.lamp_checkboxes.values():
            button.setEnabled(not is_auto)
        if is_auto:
            self.lbl_lamp_mode_hint.setText("Status lamps follow the auto cycle. Flash lamps remain manual.")
        else:
            self.lbl_lamp_mode_hint.setText("Status lamps are manual in Fixed mode. Flash lamps remain manual.")

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
        flash_lamp = 0xFF
        for key, checkbox in self.flash_lamp_checkboxes.items():
            flash_lamp = set_lamp(
                flash_lamp,
                key,
                checkbox.isChecked(),
                self.dm1_definitions,
            )

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
            flash_lamp_status=flash_lamp,
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
        data = build_dm1_frame(
            state.lamp_status,
            state.spn,
            state.fmi,
            state.occurrence,
            flash_lamp_status=state.flash_lamp_status,
        )
        self.lbl_preview.setText(format_bytes(data))

    def _send_once(self) -> None:
        if self.message is None:
            return
        self.engine.send_once(self.message)
