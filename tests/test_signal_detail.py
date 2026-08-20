import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from config_manager import Message, Signal
from gui.signal_detail import SignalDetail


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


if __name__ == "__main__":
    unittest.main()
