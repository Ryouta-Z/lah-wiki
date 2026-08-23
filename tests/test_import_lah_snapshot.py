import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.import_lah_snapshot import SOURCES, import_snapshot


class ImportLahSnapshotTest(unittest.TestCase):
    def _fake_run(self, invalid_source: str | None = None):
        def run(command, **_kwargs):
            remote_path = command[-1]
            name = next(name for name, path in SOURCES.items() if path == remote_path)
            payloads = {
                "ChineseSimplified": {"CARD_NAME_AKASHI": "赤司"},
                "CardMaster": {"1": {"heroCardId": 1, "resourceName": "akashi", "skillIds": [10]}},
                "SidekickMaster": {"2": {"sidekickCardId": 2, "resourceName": "akashi", "skillIds": [10], "equipmentSkills": []}},
                "SkillMaster": {"10": {"skillId": 10}},
            }
            payload = b"not json" if name == invalid_source else json.dumps(payloads[name]).encode()
            return SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

        return run

    def test_import_writes_all_four_validated_snapshot_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adb = root / "adb.exe"
            adb.touch()
            output = root / "snapshot"
            with patch("subprocess.run", self._fake_run()):
                written = import_snapshot(adb, "device-1", output, "20260823")

            self.assertEqual(len(written), 4)
            self.assertTrue(all(path.is_file() for path in written))

    def test_import_does_not_write_partial_snapshot_when_a_source_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adb = root / "adb.exe"
            adb.touch()
            output = root / "snapshot"
            with patch("subprocess.run", self._fake_run("SkillMaster")):
                with self.assertRaisesRegex(RuntimeError, "SkillMaster"):
                    import_snapshot(adb, "device-1", output, "20260823")

            self.assertEqual(list(output.glob("*")), [])

    def test_import_rejects_cards_with_missing_skill_references(self):
        def run(command, **_kwargs):
            remote_path = command[-1]
            name = next(name for name, path in SOURCES.items() if path == remote_path)
            payloads = {
                "ChineseSimplified": {"CARD_NAME_AKASHI": "赤司"},
                "CardMaster": {"1": {"heroCardId": 1, "resourceName": "akashi", "skillIds": [999]}},
                "SidekickMaster": {"2": {"sidekickCardId": 2, "resourceName": "akashi", "skillIds": [10], "equipmentSkills": []}},
                "SkillMaster": {"10": {"skillId": 10}},
            }
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payloads[name]).encode(),
                stderr=b"",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adb = root / "adb.exe"
            adb.touch()
            output = root / "snapshot"
            with patch("subprocess.run", run):
                with self.assertRaisesRegex(RuntimeError, "missing skill"):
                    import_snapshot(adb, "device-1", output, "20260823")

            self.assertEqual(list(output.glob("*")), [])


if __name__ == "__main__":
    unittest.main()
