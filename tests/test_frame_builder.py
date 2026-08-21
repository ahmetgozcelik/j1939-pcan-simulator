try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tests import _bootstrap  # noqa: F401
import unittest

from j1939_pcan_simulator.config.workspace import Message, Signal
from j1939_pcan_simulator.protocol.frame_builder import (
    DiagnosticTroubleCode,
    build_dm1_frame,
    build_dm1_frame_from_dtcs,
    build_frame,
    format_bytes,
    pack_signal,
    physical_to_raw,
    raw_to_physical,
)


class FrameBuilderTests(unittest.TestCase):
    def test_raw_physical_conversion(self):
        self.assertEqual(physical_to_raw(100.0, 0.5, -10.0), 220)
        self.assertEqual(raw_to_physical(220, 0.5, -10.0), 100.0)

    def test_little_endian_signal_packing(self):
        frame = bytearray(b"\x00" * 8)

        pack_signal(frame, raw=0x19, byte_pos=3, bit_pos=0, bit_length=16, byte_order="little_endian")

        self.assertEqual(format_bytes(frame), "00 00 00 19 00 00 00 00")

    def test_big_endian_signal_packing(self):
        frame = bytearray(b"\x00" * 8)

        pack_signal(frame, raw=0b1010, byte_pos=0, bit_pos=1, bit_length=4, byte_order="big_endian")

        self.assertEqual(format_bytes(frame), "02 80 00 00 00 00 00 00")

    def test_build_frame_starts_with_j1939_not_available_bytes(self):
        msg = Message(signals=[
            Signal(
                name="Engine Speed",
                byte_pos=3,
                bit_pos=0,
                bit_length=16,
                byte_order="little_endian",
                raw_min=0,
                raw_max=64255,
                raw_value=6400,
            )
        ])

        self.assertEqual(format_bytes(build_frame(msg)), "FF FF FF 00 19 FF FF FF")

    def test_dm1_single_dtc_encoding(self):
        data = build_dm1_frame(0x15, spn=100, fmi=3, oc=2)

        self.assertEqual(format_bytes(data), "15 FF 64 00 03 02 FF FF")

    def test_dm1_conversion_method_bit(self):
        data = build_dm1_frame(0x15, spn=100, fmi=3, oc=2, conversion_method=1)

        self.assertEqual(format_bytes(data), "15 FF 64 00 03 82 FF FF")

    def test_dm1_no_dtc_fills_remaining_bytes(self):
        data = build_dm1_frame_from_dtcs(0x00, [])

        self.assertEqual(format_bytes(data), "00 FF FF FF FF FF FF FF")

    def test_dm1_multiple_dtcs_require_transport_protocol(self):
        with self.assertRaisesRegex(ValueError, "Transport Protocol"):
            build_dm1_frame_from_dtcs(
                0x00,
                [
                    DiagnosticTroubleCode(100, 3, 1),
                    DiagnosticTroubleCode(101, 4, 1),
                ],
            )

    def test_dm1_rejects_invalid_dtc_fields(self):
        with self.assertRaises(ValueError):
            build_dm1_frame_from_dtcs(0x00, [DiagnosticTroubleCode(0x80000, 0, 0)])
        with self.assertRaises(ValueError):
            build_dm1_frame_from_dtcs(0x00, [DiagnosticTroubleCode(0, 32, 0)])
        with self.assertRaises(ValueError):
            build_dm1_frame_from_dtcs(0x00, [DiagnosticTroubleCode(0, 0, 127)])


if __name__ == "__main__":
    unittest.main()




