import unittest

from config_manager import Message
from j1939_id import (
    PGN_DM1,
    PGN_DM2,
    PGN_PROPRIETARY_A,
    PGN_REQUEST,
    PgnCategory,
    build_can_id,
    classify_pgn,
    format_can_id,
    is_dm1_can_id,
    is_diagnostic_dtc_can_id,
    parse_can_id,
    pgn_from_fields,
)


class J1939IdTests(unittest.TestCase):
    def test_parse_pdu2_includes_ps_in_pgn(self):
        parsed = parse_can_id("18FECA00")

        self.assertEqual(parsed.priority, 6)
        self.assertEqual(parsed.pf, 0xFE)
        self.assertEqual(parsed.ps, 0xCA)
        self.assertEqual(parsed.source_address, 0x00)
        self.assertEqual(parsed.pgn, 0x00FECA)
        self.assertTrue(parsed.is_pdu2)
        self.assertIsNone(parsed.destination_address)
        self.assertEqual(parsed.group_extension, 0xCA)

    def test_parse_pdu1_excludes_destination_from_pgn(self):
        parsed = parse_can_id("18EA2300")

        self.assertEqual(parsed.pf, 0xEA)
        self.assertEqual(parsed.ps, 0x23)
        self.assertEqual(parsed.pgn, PGN_REQUEST)
        self.assertTrue(parsed.is_pdu1)
        self.assertEqual(parsed.destination_address, 0x23)
        self.assertIsNone(parsed.group_extension)

    def test_pgn_from_fields_uses_pf_boundary(self):
        self.assertEqual(pgn_from_fields(edp=0, dp=0, pf=0xEF, ps=0xAA), 0x00EF00)
        self.assertEqual(pgn_from_fields(edp=0, dp=0, pf=0xF0, ps=0xAA), 0x00F0AA)

    def test_build_can_id_round_trip_for_pdu1(self):
        can_id = build_can_id(
            priority=6,
            pgn=PGN_REQUEST,
            source_address=0x80,
            destination_address=0x23,
        )

        self.assertEqual(format_can_id(can_id), "18EA2380")
        self.assertEqual(parse_can_id(can_id).pgn, PGN_REQUEST)

    def test_build_can_id_round_trip_for_pdu2(self):
        can_id = build_can_id(priority=6, pgn=PGN_DM1, source_address=0x80)

        self.assertEqual(format_can_id(can_id), "18FECA80")
        self.assertEqual(parse_can_id(can_id).pgn, PGN_DM1)

    def test_dm1_detection_uses_pgn_not_name(self):
        self.assertTrue(is_dm1_can_id("18FECA00"))
        self.assertTrue(Message(can_id="18FECA00", name="Not diagnostic").is_dm1())
        self.assertFalse(Message(can_id="18FEEE00", name="DM1 label only").is_dm1())
        self.assertTrue(is_diagnostic_dtc_can_id("18FECA00"))
        self.assertTrue(is_diagnostic_dtc_can_id("18FECB80"))
        self.assertTrue(Message(can_id="18FECB80", name="DM2").is_diagnostic_dtc())

    def test_pgn_categories(self):
        self.assertEqual(classify_pgn(PGN_REQUEST), PgnCategory.REQUEST)
        self.assertEqual(classify_pgn(0x00EC00), PgnCategory.TRANSPORT)
        self.assertEqual(classify_pgn(PGN_DM1), PgnCategory.DIAGNOSTIC)
        self.assertEqual(classify_pgn(PGN_DM2), PgnCategory.DIAGNOSTIC)
        self.assertEqual(classify_pgn(PGN_PROPRIETARY_A), PgnCategory.PROPRIETARY_A)
        self.assertEqual(classify_pgn(0x00FF10), PgnCategory.PROPRIETARY_B)
        self.assertEqual(classify_pgn(0x00F004), PgnCategory.STANDARD)
        self.assertEqual(classify_pgn(0x40000), PgnCategory.UNKNOWN)

    def test_invalid_can_id_rejected(self):
        with self.assertRaises(ValueError):
            parse_can_id("3FFFFFFF")
        with self.assertRaises(ValueError):
            build_can_id(priority=8, pgn=0, source_address=0)
        with self.assertRaises(ValueError):
            build_can_id(priority=6, pgn=0x00EA23, source_address=0)


if __name__ == "__main__":
    unittest.main()
