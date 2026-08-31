import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.extract_all_lah_spine import _output_is_complete, _resume_report, _targets, extract_all


class ExtractAllLahSpineTest(unittest.TestCase):
    def test_targets_keep_catalogued_characters_and_exclude_one_star_soldiers(self):
        targets = _targets(
            {
                "akashi": {"bundle": "akashi.bundle"},
                "wrestlerFire": {"bundle": "wrestler-fire.bundle"},
                "missing": {"bundle": None},
            }
        )

        self.assertEqual(targets, [("akashi", {"bundle": "akashi.bundle"})])

    def test_resume_keeps_completed_and_skipped_but_retries_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "target_count": 3,
                        "excluded_one_star_soldiers": [],
                        "completed": [{"code": "akashi"}],
                        "skipped": [{"code": "melide"}],
                        "failed": [{"code": "norbrand", "reason": "403"}],
                    }
                ),
                encoding="utf-8",
            )

            report = _resume_report(report_path, 3, [])
            already_done = {
                item["code"]
                for key in ("completed", "skipped")
                for item in report[key]
            }

            self.assertEqual(already_done, {"akashi", "melide"})
            self.assertEqual(report["failed"], [{"code": "norbrand", "reason": "403"}])

    def test_extract_all_keeps_prior_failure_while_exporting_another_character(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_dir = root / "cache"
            output_dir = root / "output"
            output_dir.mkdir()
            (cache_dir / "norbrand.bundle").parent.mkdir()
            (cache_dir / "norbrand.bundle").write_bytes(b"bundle")
            (output_dir / "report.json").write_text(
                json.dumps(
                    {
                        "target_count": 2,
                        "excluded_one_star_soldiers": [],
                        "completed": [],
                        "skipped": [],
                        "failed": [{"code": "norbrand", "reason": "403"}],
                    }
                ),
                encoding="utf-8",
            )

            def download(_client, _bundle, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"bundle")

            def skeleton_names(bundle_path):
                if bundle_path.name == "norbrand.bundle":
                    raise ValueError("still unavailable")
                return ["spine_akashi_SkeletonData"]

            def export(_bundle, destination, _skeleton):
                return SimpleNamespace(output_dir=destination, animations=("Idle",))

            with (
                patch("scripts.extract_all_lah_spine._download", side_effect=download),
                patch("scripts.extract_all_lah_spine._skeleton_names", side_effect=skeleton_names),
                patch("scripts.extract_all_lah_spine.extract", side_effect=export),
            ):
                report = extract_all(
                    {"akashi": {"bundle": "akashi.bundle"}, "norbrand": {"bundle": "norbrand.bundle"}},
                    cache_dir,
                    output_dir,
                )

            self.assertEqual([item["code"] for item in report["completed"]], ["akashi"])
            self.assertEqual(report["failed"], [{"code": "norbrand", "reason": "still unavailable"}])

    def test_extract_all_rejects_unsafe_skeleton_name_before_exporting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_dir = root / "cache"
            cache_dir.mkdir()
            (cache_dir / "akashi.bundle").write_bytes(b"bundle")

            with patch(
                "scripts.extract_all_lah_spine._skeleton_names", return_value=["../outside"]
            ):
                report = extract_all(
                    {"akashi": {"bundle": "akashi.bundle"}}, cache_dir, root / "output"
                )

            self.assertEqual(len(report["completed"]), 0)
            self.assertEqual(report["failed"][0]["code"], "akashi")
            self.assertIn("Unsafe SkeletonData name", report["failed"][0]["reason"])

    def test_extract_all_reports_catalogued_character_without_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            report = extract_all(
                {"akashi": {"bundle": None}}, Path(directory) / "cache", Path(directory) / "output"
            )

            self.assertEqual(report["not_exportable"], [{"code": "akashi", "reason": "no_bundle"}])

    def test_extract_all_rejects_unsafe_character_code_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = extract_all(
                {"../outside": {"bundle": "akashi.bundle"}}, root / "cache", root / "output"
            )

            self.assertEqual(report["failed"][0]["code"], "../outside")
            self.assertIn("Unsafe character code", report["failed"][0]["reason"])

    def test_complete_output_requires_manifest_referenced_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exported = root / "akashi"
            exported.mkdir()
            (exported / "skeleton.json").write_text(
                json.dumps({"animations": {"Idle": {}}}), encoding="utf-8"
            )
            (exported / "atlas.atlas").write_text("page.png\n", encoding="utf-8")
            (exported / "page.png").write_bytes(b"png")
            (exported / "manifest.json").write_text(
                json.dumps(
                    {
                        "skeleton": {"file": "skeleton.json"},
                        "animations": ["Idle"],
                        "atlases": [{"file": "atlas.atlas"}],
                        "textures": [{"file": "page.png"}],
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(_output_is_complete({"outputs": [{"directory": "akashi"}]}, root))
            (exported / "page.png").unlink()
            self.assertFalse(_output_is_complete({"outputs": [{"directory": "akashi"}]}, root))


if __name__ == "__main__":
    unittest.main()
