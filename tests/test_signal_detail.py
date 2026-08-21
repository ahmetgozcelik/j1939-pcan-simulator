import _bootstrap  # noqa: F401
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from j1939_pcan_simulator.config.workspace import Message, Signal
from j1939_pcan_simulator.gui.signal_detail import SignalDetail


class SignalDetailValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_zero_scale_shows_inline_error(self):
        detail = SignalDetail()
        detail.set_signal(Message(), Signal(scale=0))

        self.assertFalse(detail.lbl_scale_error.isHidden())
        self.assertIn("zero", detail.spin_scale.toolTip().lower())

    def test_nonzero_scale_hides_inline_error(self):
        detail = SignalDetail()
        detail.set_signal(Message(), Signal(scale=1))

        self.assertTrue(detail.lbl_scale_error.isHidden())
        self.assertEqual(detail.spin_scale.toolTip(), "")

    def test_raw_editor_accepts_unsigned_32_bit_ranges(self):
        detail = SignalDetail()
        signal = Signal(bit_length=32, raw_max=4211081215, raw_value=20000)

        detail.set_signal(Message(signals=[signal]), signal)

        self.assertEqual(detail.pair_max.raw(), 4211081215)


if __name__ == "__main__":
    unittest.main()


