import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_vercel_readonly import build_vercel_readonly, validate_deployment_package


class VercelReadonlyTest(unittest.TestCase):
    def _catalog(self) -> dict:
        return {
            "metadata": {"snapshotId": "fixture", "heroCardCount": 1, "sidekickCardCount": 1},
            "cards": [
                {
                    "key": "hero:1",
                    "kind": "hero",
                    "name": "英雄样例",
                    "avatar": {"status": "available", "code": "hero-sample"},
                    "aliases": [],
                    "skills": [],
                    "skillUpgrades": [],
                    "stats": {"level60": {}},
                },
                {
                    "key": "sidekick:1",
                    "kind": "sidekick",
                    "name": "助手样例",
                    "avatar": {"status": "available", "code": "sidekick-sample"},
                    "aliases": [],
                    "skills": [],
                    "skillUpgrades": [],
                    "stats": {"max": {}},
                    "tags": [{"id": "sample-tag", "label": "样例", "path": ["分类", "样例"]}],
                },
            ],
            "skills": [],
            "skillUpgrades": [],
            "statusTerms": [],
            "assistantTags": [{"id": "sample-tag", "label": "样例", "parentId": None}],
            "heroTags": [],
        }

    def test_builds_a_static_readonly_package_without_admin_or_local_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog.json"
            catalog = self._catalog()
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            icon_dir = root / "icons"
            icon_dir.mkdir()
            (icon_dir / "hero-sample.png").write_bytes(b"hero image")
            (icon_dir / "sidekick-sample.png").write_bytes(b"sidekick image")

            output_dir = root / "vercel-readonly"
            summary = build_vercel_readonly(output_dir, catalog_path, icon_dir)
            html = (output_dir / "index.html").read_text(encoding="utf-8")

            self.assertEqual(summary["avatars"], 2)
            self.assertTrue((output_dir / "assets/images/icon/hero-sample.png").is_file())
            self.assertTrue((output_dir / "assets/images/icon/sidekick-sample.png").is_file())
            self.assertIn("const catalog =", html)
            self.assertIn('id="hero-tags"', html)
            self.assertIn('id="assistant-tags"', html)
            self.assertIn('<body class="official-card-layout">', html)
            self.assertIn("avatarMarkup", html)
            self.assertNotIn('id="tagSettings"', html)
            self.assertNotIn("127.0.0.1", html)
            self.assertNotIn("fetch(", html)
            self.assertEqual(validate_deployment_package(output_dir, catalog)["avatars"], 2)

    def test_refuses_to_replace_an_unmarked_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog.json"
            catalog_path.write_text(json.dumps(self._catalog(), ensure_ascii=False), encoding="utf-8")
            icon_dir = root / "icons"
            icon_dir.mkdir()
            (icon_dir / "hero-sample.png").write_bytes(b"hero image")
            (icon_dir / "sidekick-sample.png").write_bytes(b"sidekick image")
            output_dir = root / "vercel-readonly"
            output_dir.mkdir()
            (output_dir / "manual-file.txt").write_text("do not replace", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "拒绝覆盖"):
                build_vercel_readonly(output_dir, catalog_path, icon_dir)
