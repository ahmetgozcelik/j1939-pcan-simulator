import tempfile
import unittest
from pathlib import Path

from tools.prepare_public_repo import prepare_public_repo


class PublicRepoExportTests(unittest.TestCase):
    def test_export_contains_only_public_release_materials(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "public"

            prepare_public_repo(output, include_exe=False)

            self.assertTrue((output / "README.md").exists())
            self.assertTrue((output / "RELEASE_NOTES.md").exists())
            self.assertTrue((output / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").exists())
            self.assertTrue((output / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").exists())
            self.assertTrue((output / ".github" / "ISSUE_TEMPLATE" / "pcan_support.yml").exists())
            self.assertFalse((output / "release-assets" / "J1939_Simulator.exe").exists())

            exported_files = [path for path in output.rglob("*") if path.is_file()]
            self.assertTrue(exported_files)
            self.assertFalse(any(path.suffix == ".py" for path in exported_files))
            self.assertFalse(any("configs" in path.relative_to(output).parts for path in exported_files))


if __name__ == "__main__":
    unittest.main()
