import _bootstrap  # noqa: F401
import unittest

from j1939_pcan_simulator.transport.can_bus import build_bus_kwargs, connection_info, normalize_backend


class CanInterfaceSettingsTests(unittest.TestCase):
    def test_pcan_backend_kwargs_include_bitrate(self):
        kwargs = build_bus_kwargs("pcan", "PCAN_USBBUS1", 250000)

        self.assertEqual(kwargs["interface"], "pcan")
        self.assertEqual(kwargs["channel"], "PCAN_USBBUS1")
        self.assertEqual(kwargs["bitrate"], 250000)

    def test_virtual_backend_kwargs_are_hardware_free(self):
        kwargs = build_bus_kwargs("virtual", "j1939-simulator", 250000)

        self.assertEqual(kwargs["interface"], "virtual")
        self.assertEqual(kwargs["channel"], "j1939-simulator")
        self.assertNotIn("bitrate", kwargs)

    def test_backend_normalization_rejects_unknown_values(self):
        self.assertEqual(normalize_backend("PCAN"), "pcan")
        with self.assertRaises(ValueError):
            normalize_backend("unknown")

    def test_connection_info_labels_virtual_backend(self):
        self.assertEqual(connection_info("virtual", "j1939-simulator", 250000), "virtual:j1939-simulator")
        self.assertEqual(connection_info("pcan", "PCAN_USBBUS1", 250000), "PCAN_USBBUS1 @ 250000 bit/s")


if __name__ == "__main__":
    unittest.main()


