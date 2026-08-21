try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tests import _bootstrap  # noqa: F401
import unittest

from j1939_pcan_simulator.config.workspace import Message, Signal, Workspace, default_workspace
from j1939_pcan_simulator.validation.workspace import has_errors, signal_bit_positions, validate_signal, validate_workspace


class WorkspaceValidationTests(unittest.TestCase):
    def test_duplicate_can_id_is_error(self):
        ws = Workspace(messages=[
            Message(can_id="18F00400", name="EEC1"),
            Message(can_id="18F00400", name="Duplicate EEC1"),
        ])

        codes = {issue.code for issue in validate_workspace(ws)}

        self.assertIn("duplicate_can_id", codes)

    def test_invalid_can_id_is_error(self):
        ws = Workspace(messages=[Message(can_id="3FFFFFFF")])

        issues = validate_workspace(ws)

        self.assertIn("invalid_can_id", {issue.code for issue in issues})
        self.assertTrue(has_errors(issues))

    def test_signal_out_of_frame_is_error(self):
        sig = Signal(byte_pos=7, bit_pos=4, bit_length=8)

        codes = {issue.code for issue in validate_signal(sig)}

        self.assertIn("signal_out_of_frame", codes)

    def test_signal_overlap_is_error(self):
        ws = Workspace(messages=[Message(signals=[
            Signal(name="a", byte_pos=0, bit_pos=0, bit_length=8),
            Signal(name="b", byte_pos=0, bit_pos=7, bit_length=2),
        ])])

        codes = {issue.code for issue in validate_workspace(ws)}

        self.assertIn("signal_overlap", codes)

    def test_raw_range_must_fit_bit_length(self):
        sig = Signal(bit_length=8, raw_min=0, raw_max=300, raw_value=20)

        codes = {issue.code for issue in validate_signal(sig)}

        self.assertIn("raw_range_exceeds_bit_length", codes)

    def test_raw_value_must_be_inside_range(self):
        sig = Signal(bit_length=8, raw_min=10, raw_max=20, raw_value=30)

        codes = {issue.code for issue in validate_signal(sig)}

        self.assertIn("raw_value_out_of_range", codes)

    def test_zero_scale_is_error(self):
        sig = Signal(scale=0)

        codes = {issue.code for issue in validate_signal(sig)}

        self.assertIn("zero_scale", codes)

    def test_big_endian_positions_follow_packer_order(self):
        sig = Signal(byte_pos=0, bit_pos=1, bit_length=4, byte_order="big_endian")

        self.assertEqual(list(signal_bit_positions(sig)), [1, 0, 15, 14])

    def test_default_workspace_has_no_validation_errors(self):
        issues = validate_workspace(default_workspace())

        self.assertFalse(has_errors(issues), [f"{i.code}: {i.message}" for i in issues])


if __name__ == "__main__":
    unittest.main()




