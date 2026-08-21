import _bootstrap  # noqa: F401
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from j1939_pcan_simulator.config.workspace import Message, Signal, Workspace
from j1939_pcan_simulator.gui.log_panel import LogPanel
from j1939_pcan_simulator.gui.message_panel import MessagePanel
from j1939_pcan_simulator.gui.signal_panel import SignalPanel


class MessagePanelBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_add_message_uses_unique_j1939_id(self):
        ws = Workspace(messages=[Message(can_id="18FF0000")])
        panel = MessagePanel()
        panel.set_workspace(ws)

        panel._add_message()

        self.assertEqual(ws.messages[1].can_id, "18FF0001")
        self.assertEqual(ws.messages[1].name, "New J1939 Message")

    def test_duplicate_message_suggests_unique_source_address(self):
        ws = Workspace(messages=[Message(can_id="18F00400", name="EEC1")])
        panel = MessagePanel()
        panel.set_workspace(ws)

        panel._duplicate_message()

        self.assertEqual(ws.messages[1].can_id, "18F00401")
        self.assertFalse(ws.messages[1].active)

    def test_delete_active_message_requests_stop_before_removal(self):
        ws = Workspace(messages=[Message(can_id="18F00400", active=True)])
        panel = MessagePanel()
        panel.set_workspace(ws)
        stopped = []
        panel.request_active_changed.connect(stopped.append)

        panel._delete_message()

        self.assertEqual(len(ws.messages), 0)
        self.assertEqual(len(stopped), 1)
        self.assertFalse(stopped[0].active)

    def test_start_button_label_matches_active_semantics(self):
        panel = MessagePanel()

        self.assertEqual(panel.btn_start_all.text(), "Start Active")

    def test_new_message_name_updates_when_pgn_becomes_dm2(self):
        ws = Workspace(messages=[Message(can_id="18FF0080", name="New J1939 Message")])
        panel = MessagePanel()
        panel.set_workspace(ws)

        self.assertTrue(panel.model.setData(panel.model.index(0, 2), "0FECB"))

        self.assertEqual(ws.messages[0].name, "DM2 - Previously Active Diagnostic Trouble Codes")

    def test_add_signal_uses_first_free_byte(self):
        msg = Message(signals=[
            Signal(byte_pos=0, bit_pos=0, bit_length=8),
            Signal(byte_pos=2, bit_pos=0, bit_length=8),
        ])
        panel = SignalPanel()
        panel.set_message(msg)

        panel._add_signal()

        self.assertEqual(msg.signals[-1].byte_pos, 1)
        self.assertEqual(msg.signals[-1].bit_pos, 0)

    def test_clear_only_clears_visible_log_text(self):
        panel = LogPanel()
        panel.view.appendPlainText("sample")

        panel.clear()

        self.assertEqual(panel.view.toPlainText(), "")


if __name__ == "__main__":
    unittest.main()


