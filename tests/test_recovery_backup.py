import _bootstrap  # noqa: F401
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from j1939_pcan_simulator.config import workspace as cfg
from j1939_pcan_simulator.config.workspace import Message, Workspace, load, save_recovery_backup


class RecoveryBackupTests(unittest.TestCase):
    def test_recovery_backup_round_trips_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            recovery_dir = Path(tmp) / "recovery"
            with patch.object(cfg, "RECOVERY_DIR", recovery_dir):
                path = save_recovery_backup(
                    Workspace(messages=[Message(can_id="18FECA00", name="DM1")]),
                    "before_new",
                    "source.json",
                )

                self.assertIsNotNone(path)
                self.assertTrue(path.exists())
                restored = load(path)
                self.assertEqual(restored.messages[0].can_id, "18FECA00")

    def test_empty_workspace_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            recovery_dir = Path(tmp) / "recovery"
            with patch.object(cfg, "RECOVERY_DIR", recovery_dir):
                path = save_recovery_backup(Workspace(), "before_new")

                self.assertIsNone(path)
                self.assertFalse(recovery_dir.exists())

    def test_recovery_prunes_old_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            recovery_dir = Path(tmp) / "recovery"
            with patch.object(cfg, "RECOVERY_DIR", recovery_dir):
                for index in range(3):
                    save_recovery_backup(
                        Workspace(messages=[Message(can_id=f"18FF00{index:02X}")]),
                        f"before_new_{index}",
                        max_backups=2,
                    )

                self.assertEqual(len(list(recovery_dir.glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()


