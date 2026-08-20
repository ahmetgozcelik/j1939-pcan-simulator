import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QAbstractButton, QGroupBox, QLabel

from dm1_definitions import (
    build_lamp_status,
    get_lamp,
    load_dm1_definitions,
    set_lamp,
)
from gui.dm1_panel import DM1Panel
from simulator_engine import DM1State


class FakeEngine:
    def __init__(self):
        self.state = DM1State()

    def get_dm1_state(self, can_id):
        return self.state

    def set_dm1_state(self, can_id, state):
        self.state = state

    def send_once(self, message):
        return None


class DM1DefinitionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_loads_external_lamp_labels_and_fmi_descriptions(self):
        payload = {
            "lamp_statuses": [
                {"key": "custom_red", "label": "Custom Red Lamp", "bit": 4},
                {"key": "custom_mil", "label": "Custom MIL", "bit": 6},
            ],
            "fmi_descriptions": {"3": "Custom voltage high"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dm1_definitions.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            definitions = load_dm1_definitions(path)

        self.assertEqual([lamp.label for lamp in definitions.lamps], ["Custom Red Lamp", "Custom MIL"])
        self.assertEqual(definitions.fmi_descriptions[3], "Custom voltage high")

    def test_rejects_non_standard_dm1_lamp_bit_positions(self):
        payload = {
            "lamp_statuses": [
                {"key": "bad", "label": "Bad Lamp", "bit": 1},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dm1_definitions.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            definitions = load_dm1_definitions(path)

        self.assertEqual(definitions.lamps[0].key, "red")

    def test_lamp_helpers_use_configured_bit_positions(self):
        definitions = load_dm1_definitions()

        lamp = set_lamp(0xFF, "red", True, definitions)

        self.assertTrue(get_lamp(lamp, "red", definitions))
        self.assertFalse(get_lamp(lamp, "amber", definitions))
        self.assertEqual(build_lamp_status(["red", "amber"], definitions), 0x14)

    def test_dm1_panel_visible_text_is_english(self):
        panel = DM1Panel(FakeEngine())
        visible_text = [
            panel.cmb_lamp_mode.itemText(i) for i in range(panel.cmb_lamp_mode.count())
        ]
        visible_text += [
            panel.cmb_spn_mode.itemText(i) for i in range(panel.cmb_spn_mode.count())
        ]
        visible_text += [
            box.title()
            for box in panel.findChildren(QGroupBox)
        ]
        visible_text += [
            label.text()
            for label in panel.findChildren(QLabel)
        ]
        visible_text += [
            button.text()
            for button in panel.findChildren(QAbstractButton)
        ]

        joined = "\n".join(visible_text)
        for forbidden in ("Simulasyon", "Simülasyon", "Degisim", "Değişim", "Detay", "Liste", "Aralik", "Aralık"):
            self.assertNotIn(forbidden, joined)

    def test_lamp_status_controls_are_readable_and_externalized(self):
        panel = DM1Panel(FakeEngine())

        self.assertEqual(panel.btn_open_definitions.text(), "Edit JSON...")
        self.assertEqual(panel.btn_reload_definitions.text(), "Reload JSON")
        self.assertIn("Definition file:", panel.lbl_definitions_status.text())
        for checkbox in panel.lamp_checkboxes.values():
            self.assertGreaterEqual(checkbox.minimumWidth(), 280)

    def test_reload_reports_what_changed(self):
        panel = DM1Panel(FakeEngine())

        panel._reload_definitions()

        self.assertIn("Reloaded", panel.lbl_definitions_status.text())


if __name__ == "__main__":
    unittest.main()
