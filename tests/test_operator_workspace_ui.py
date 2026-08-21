import _bootstrap  # noqa: F401
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QHeaderView, QScrollArea

from j1939_pcan_simulator.config.workspace import Message, Workspace
from j1939_pcan_simulator.gui.log_panel import LogPanel
from j1939_pcan_simulator.gui.main_window import MainWindow, validation_status_text
from j1939_pcan_simulator.gui.message_panel import (
    COL_DA_GE,
    COL_ID,
    COL_NAME,
    COL_PGN,
    COL_PGN_DEC,
    COL_PRIORITY,
    COL_SA,
    COL_TYPE,
    MessagePanel,
)
from j1939_pcan_simulator.gui.signal_panel import COL_NAME as SIGNAL_COL_NAME, SignalPanel
from j1939_pcan_simulator.gui.signal_detail import SignalDetail


class OperatorWorkspaceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_message_table_exposes_j1939_fields_for_pdu2(self):
        ws = Workspace(messages=[Message(can_id="18FECA00")])
        panel = MessagePanel()
        panel.set_workspace(ws)
        model = panel.model

        self.assertEqual(model.data(model.index(0, COL_PGN), Qt.DisplayRole), "0FECA")
        self.assertEqual(model.data(model.index(0, COL_PGN_DEC), Qt.DisplayRole), 65226)
        self.assertEqual(model.data(model.index(0, COL_PRIORITY), Qt.DisplayRole), 6)
        self.assertEqual(model.data(model.index(0, COL_SA), Qt.DisplayRole), "00")
        self.assertEqual(model.data(model.index(0, COL_DA_GE), Qt.DisplayRole), "GE CA")
        self.assertEqual(model.data(model.index(0, COL_TYPE), Qt.DisplayRole), "diagnostic")

    def test_message_table_exposes_destination_for_pdu1(self):
        ws = Workspace(messages=[Message(can_id="18EA2380")])
        panel = MessagePanel()
        panel.set_workspace(ws)
        model = panel.model

        self.assertEqual(model.data(model.index(0, COL_PGN), Qt.DisplayRole), "0EA00")
        self.assertEqual(model.data(model.index(0, COL_DA_GE), Qt.DisplayRole), "DA 23")
        self.assertEqual(model.data(model.index(0, COL_TYPE), Qt.DisplayRole), "request")

    def test_type_column_explains_that_type_is_derived_from_pgn(self):
        panel = MessagePanel()
        panel.set_workspace(Workspace(messages=[Message(can_id="18FECA00")]))

        tooltip = panel.model.headerData(COL_TYPE, Qt.Horizontal, Qt.ToolTipRole)

        self.assertIn("Derived from the J1939 PGN/CAN ID", tooltip)
        self.assertFalse(panel.model.flags(panel.model.index(0, COL_TYPE)) & Qt.ItemIsEditable)

    def test_message_table_allows_editing_hex_pgn_and_rebuilds_can_id(self):
        ws = Workspace(messages=[Message(can_id="18F00480")])
        panel = MessagePanel()
        panel.set_workspace(ws)

        self.assertTrue(panel.model.setData(panel.model.index(0, COL_PGN), "0FEEF"))

        self.assertEqual(ws.messages[0].can_id, "18FEEF80")
        self.assertEqual(panel.model.data(panel.model.index(0, COL_PGN), Qt.DisplayRole), "0FEEF")
        self.assertEqual(panel.model.data(panel.model.index(0, COL_PGN_DEC), Qt.DisplayRole), 65263)

    def test_message_table_allows_editing_decimal_pgn_and_rebuilds_can_id(self):
        ws = Workspace(messages=[Message(can_id="18F00480")])
        panel = MessagePanel()
        panel.set_workspace(ws)

        self.assertTrue(panel.model.setData(panel.model.index(0, COL_PGN_DEC), "65263"))

        self.assertEqual(ws.messages[0].can_id, "18FEEF80")
        self.assertEqual(panel.model.data(panel.model.index(0, COL_PGN), Qt.DisplayRole), "0FEEF")

    def test_message_and_signal_name_columns_are_user_resizable(self):
        msg_panel = MessagePanel()
        self.assertEqual(
            msg_panel.table.horizontalHeader().sectionResizeMode(COL_NAME),
            QHeaderView.Interactive,
        )
        self.assertGreaterEqual(msg_panel.table.columnWidth(COL_NAME), 220)

        sig_panel = SignalPanel()
        self.assertEqual(
            sig_panel.table.horizontalHeader().sectionResizeMode(SIGNAL_COL_NAME),
            QHeaderView.Interactive,
        )
        self.assertGreaterEqual(sig_panel.table.columnWidth(SIGNAL_COL_NAME), 240)

    def test_log_filter_shows_only_errors_when_selected(self):
        panel = LogPanel()
        panel.send_error("18FECA00", "driver missing")
        panel.combo_filter.setCurrentIndex(panel.combo_filter.findData("error"))

        text = panel.view.toPlainText()
        self.assertIn("TX-FAIL", text)
        self.assertNotIn(" TX ", text)

    def test_log_text_filter_matches_can_id_or_pgn_text(self):
        panel = LogPanel()
        panel.send_error("18FECA00", "driver missing")
        panel.send_error("18F00400", "other")

        panel.edt_filter.setText("FECA")

        text = panel.view.toPlainText()
        self.assertIn("18FECA00", text)
        self.assertNotIn("18F00400", text)

    def test_signal_detail_shows_j1939_summary_without_signal(self):
        detail = SignalDetail()
        detail.set_signal(Message(can_id="18FECA00"), None)

        self.assertEqual(detail.lbl_j1939_pgn.text(), "0FECA")
        self.assertEqual(detail.lbl_j1939_pgn_dec.text(), "65226")
        self.assertEqual(detail.lbl_j1939_type.text(), "diagnostic")
        self.assertTrue(detail.grp_identity.isEnabled() is False)
        self.assertTrue(detail.grp_j1939.isEnabled())
        self.assertEqual(detail.edt_name.text(), "")

    def test_signal_detail_clears_stale_fields_for_dm1_message(self):
        detail = SignalDetail()
        detail.set_signal(Message(can_id="18F00480"), Message(can_id="18F00480").signals[0] if False else None)
        detail.edt_name.setText("Stale Signal")

        detail.set_signal(Message(can_id="18FECA80"), None)

        self.assertEqual(detail.title.text(), "Diagnostic DTC message selected")
        self.assertEqual(detail.edt_name.text(), "")

    def test_diagnostic_editor_is_scrollable_in_workspace(self):
        window = MainWindow()
        try:
            window._on_message_selected(Message(can_id="18FECA80"))

            current = window.center_stack.currentWidget()
            self.assertIsInstance(current, QScrollArea)
            self.assertIs(current.widget(), window.dm1_panel)
            self.assertTrue(current.widgetResizable())
            self.assertEqual(current.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        finally:
            window.pcan.shutdown()
            window.io_worker.shutdown()
            window.close()

    def test_validation_status_text_summarizes_workspace_errors(self):
        ok_text = validation_status_text(Workspace(messages=[Message(can_id="18FECA00")]))
        bad_text = validation_status_text(Workspace(messages=[Message(can_id="3FFFFFFF")]))

        self.assertEqual(ok_text, "Validation: OK")
        self.assertIn("1 error", bad_text)


if __name__ == "__main__":
    unittest.main()


