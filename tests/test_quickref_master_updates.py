import json
import tempfile
import unittest
from pathlib import Path

from scripts.lah_quickref import (
    DEFAULT_MASTER_UPDATES_PATH,
    DEFAULT_SNAPSHOT_DIR,
    build_catalog,
    rebuild_quickref,
    write_static_site,
)


class QuickrefMasterUpdatesTest(unittest.TestCase):
    def test_supplement_adds_reviewed_cards_and_preserves_other_cards(self):
        baseline = build_catalog(DEFAULT_SNAPSHOT_DIR)
        updated = build_catalog(
            DEFAULT_SNAPSHOT_DIR, master_updates_path=DEFAULT_MASTER_UPDATES_PATH
        )
        before = {card["key"]: card for card in baseline["cards"]}
        after = {card["key"]: card for card in updated["cards"]}
        self.assertEqual(updated["metadata"]["heroCardCount"], 211)
        self.assertEqual(updated["metadata"]["sidekickCardCount"], 158)
        self.assertEqual(updated["metadata"]["skillUpgradeCount"], 66)
        self.assertEqual(updated["metadata"]["supplementalData"]["sourceKind"], "official_game_local_cache_and_approved_review")
        self.assertEqual(after.keys() - before.keys(), {
            "hero:104116", "hero:104216", "hero:104416",
            "sidekick:104116", "sidekick:104216", "sidekick:104416",
            "hero:123622", "hero:130412", "hero:133513",
            "sidekick:130416", "sidekick:133516",
        })
        for key, card in before.items():
            if key not in {"hero:103322", "hero:103222"}:
                self.assertEqual(after[key], card, key)
        for stock, name in (("10411", "火之狼人"), ("10421", "水之狼人"), ("10441", "光之狼人")):
            for kind in ("hero", "sidekick"):
                card = after[f"{kind}:{stock}6"]
                self.assertEqual(card["name"], name)
                self.assertEqual(card["nameSource"], "官方简中")
                self.assertEqual(card["avatar"]["status"], "available")
            self.assertNotEqual(
                after[f"hero:{stock}6"]["avatar"]["filename"],
                after[f"sidekick:{stock}6"]["avatar"]["filename"],
            )
        for key, quest in (("hero:103222", "302021"), ("hero:103322", "302022")):
            self.assertEqual(len(after[key]["skillUpgrades"]), 3)
            self.assertEqual({row["questId"] for row in after[key]["skillUpgrades"]}, {quest})
            for row in after[key]["skillUpgrades"]:
                self.assertNotEqual(row["after"]["descriptionSource"], "官方简中")

        for key in ("hero:123622", "hero:130412", "hero:133513", "sidekick:130416", "sidekick:133516"):
            card = after[key]
            self.assertEqual(card["nameSource"], "审核暂译")
            self.assertEqual(card["avatar"]["status"], "available")
            for skill in card["skills"]:
                self.assertEqual(skill["descriptionSource"], "审核暂译")
                self.assertTrue(skill["originalDescription"])
        self.assertEqual(next(s for s in after["hero:130412"]["skills"] if s["skillId"] == "1304104")["viewCost"], 7500)
        self.assertIn("每5连击", next(s for s in after["hero:123622"]["skills"] if s["skillId"] == "8236205")["description"])

    def test_supplement_does_not_override_a_different_base_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "updates.json"
            updates = json.loads(DEFAULT_MASTER_UPDATES_PATH.read_text(encoding="utf-8"))
            updates["baseSnapshotId"] = "another-snapshot"
            path.write_text(json.dumps(updates), encoding="utf-8")
            catalog = build_catalog(DEFAULT_SNAPSHOT_DIR, master_updates_path=path)
        self.assertEqual(catalog["metadata"]["heroCardCount"], 205)
        self.assertNotIn("supplementalData", catalog["metadata"])

    def test_tag_rebuild_keeps_the_supplement(self):
        with tempfile.TemporaryDirectory(dir=DEFAULT_SNAPSHOT_DIR.parent) as directory:
            root = Path(directory)
            catalog = rebuild_quickref(
                catalog_path=root / "catalog.json", site_path=root / "index.html"
            )
            self.assertEqual(catalog["metadata"]["skillUpgradeCount"], 66)
            html = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("火之狼人", html)
            self.assertIn("1033207", html)
            self.assertIn("宁静之舞（暂译；バイレクェ・トラエカルマ）", html)
            skill = next(row["after"] for row in catalog["skillUpgrades"] if row["after"]["skillId"] == "1033207")
            self.assertIn("含暂译名", skill["descriptionSource"])
            self.assertNotEqual(skill["officialChineseAvailability"], "完整官方简中")

    def test_refresh_keeps_the_existing_custom_query_interface(self):
        catalog = build_catalog(
            DEFAULT_SNAPSHOT_DIR, master_updates_path=DEFAULT_MASTER_UPDATES_PATH
        )
        prefix = '<style>.custom-layout { color: red; }</style>\n<script>\n'
        suffix = '\n// 查询界面层：保留现有交互\n</script>'
        with tempfile.TemporaryDirectory(dir=DEFAULT_SNAPSHOT_DIR.parent) as directory:
            path = Path(directory) / "index.html"
            path.write_text(prefix + '    const catalog = {};'+ suffix, encoding="utf-8")
            write_static_site(catalog, path)
            html = path.read_text(encoding="utf-8")
        self.assertEqual(
            html,
            prefix + '    const catalog = ' + json.dumps(catalog, ensure_ascii=False) + ';' + suffix,
        )


if __name__ == "__main__":
    unittest.main()
