import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_vercel_readonly import build_vercel_readonly, validate_deployment_package


class UpdateNotesDistributionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = {"metadata": {}, "cards": [], "heroTags": [], "assistantTags": [], "statusTerms": [], "skills": [], "skillUpgrades": []}
        catalog_path = self.root / "catalog.json"
        catalog_path.write_text(json.dumps(self.catalog), encoding="utf-8")
        self.package = self.root / "public"
        build_vercel_readonly(self.package, catalog_path, self.root / "empty-icons")

    def tearDown(self):
        self.temp.cleanup()

    def test_historical_note_images_are_retained_without_current_catalog_cards(self):
        notes_dir = self.package / "更新笔记"
        self.assertEqual({p.name for p in notes_dir.iterdir()}, {"20261008-heroes-blues.html", "style.css", "update-meta.json"})
        notes = (notes_dir / "20261008-heroes-blues.html").read_text(encoding="utf-8")
        self.assertLess(notes.index('id="update-4bdfb98"'), notes.index('id="update-6e9febd"'))
        self.assertIn('../index.html?reminder=show', notes)
        self.assertNotIn("../../data/", notes)
        for filename in ("alendblues2610.png", "thuban.png", "ceph.png", "thuban-sidekick.png", "ceph-sidekick.png"):
            self.assertTrue((self.package / "assets/images/icon" / filename).is_file())
        self.assertEqual(validate_deployment_package(self.package, self.catalog)["avatars"], 0)

    def test_missing_note_dependency_fails_package_validation(self):
        (self.package / "assets/images/icon/thuban.png").unlink()
        with self.assertRaisesRegex(ValueError, "资源缺失或越界"):
            validate_deployment_package(self.package, self.catalog)

    def test_missing_latest_anchor_fails_package_validation(self):
        note = self.package / "更新笔记/20261008-heroes-blues.html"
        note.write_text(note.read_text(encoding="utf-8").replace('id="update-4bdfb98"', 'id="wrong-anchor"'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "定位入口缺失"):
            validate_deployment_package(self.package, self.catalog)


if __name__ == "__main__":
    unittest.main()
