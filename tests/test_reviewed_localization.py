import json
import tempfile
import unittest
from pathlib import Path

from scripts.lah_quickref import build_catalog, render_static_html
from tests import test_lah_quickref as fixtures


class ReviewedLocalizationTest(unittest.TestCase):
    def build(self, directory, translations, localized=None, triggered=False, terms=None):
        fixtures.LahQuickrefTest()._write_snapshot(directory)
        hero_cards = json.loads((directory / "CardMaster-20260815").read_text(encoding="utf-8"))
        if triggered:
            for card in hero_cards.values():
                if card.get("cardName") == "アカシ":
                    card["reviewTriggeredSkillIds"] = [1001103]
        updates = directory / "updates.json"
        updates.write_text(json.dumps({
            "id": "reviewed", "baseSnapshotId": "20260815", "source": {},
            "heroCards": hero_cards, "sidekickCards": {}, "skills": {},
            "localized": localized or {}, "reviewedTranslations": translations,
            "reviewedStatusTerms": terms or {},
        }, ensure_ascii=False), encoding="utf-8")
        return build_catalog(
            directory, aliases_path=directory / "aliases.json",
            char_map_path=directory / "char_map.json", icon_dir=directory / "icons",
            master_updates_path=updates,
        )

    def test_approved_draft_is_distinct_from_official_chinese(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = self.build(Path(folder), {
                "SKILL_NAME_1001103": {"value": "已审名称", "reviewStatus": "approved"},
                "SKILL_DESCRIPTION_1001103": {"value": "已审数值110%。", "reviewStatus": "approved"},
                "SKILL_DESCRIPTION_1001101": {"value": "不能替代官中", "reviewStatus": "approved"},
                "SKILL_NAME_1001104": {"value": "尚未审核", "reviewStatus": "pending"},
            }, triggered=True)
            card = next(c for c in catalog["cards"] if c["originalName"] == "アカシ")
            skill = next(s for s in card["skills"] if s["skillId"] == "1001103")
            self.assertEqual(skill["description"], "已审数值110%。")
            self.assertEqual(skill["nameSource"], "审核暂译")
            self.assertEqual(skill["officialChineseAvailability"], "无官方简中（已审核暂译）")
            self.assertTrue(skill["originalDescription"])
            self.assertTrue(any(s["relation"] == "触发技能" for s in card["skills"]))
            official = next(s for s in card["skills"] if s["skillId"] == "1001101")
            self.assertEqual(official["descriptionSource"], "官方简中")
            self.assertNotEqual(official["description"], "不能替代官中")
            self.assertFalse(any(s["name"] == "尚未审核" for s in card["skills"]))
            self.assertIn("中文暂译（已审核；游戏尚无官方简中）", render_static_html(catalog))

    def test_supplemental_official_chinese_takes_priority(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = self.build(Path(folder), {
                "SKILL_DESCRIPTION_1001103": {"value": "过期暂译", "reviewStatus": "approved"},
            }, localized={"SKILL_DESCRIPTION_1001103": "本次官中已补齐。"})
            skill = next(s for s in catalog["skills"] if s["skillId"] == "1001103")
            self.assertEqual(skill["description"], "本次官中已补齐。")
            self.assertEqual(skill["descriptionSource"], "官方简中")
            self.assertNotIn("originalDescription", skill)

    def test_translated_text_relinks_official_and_reviewed_mechanics(self):
        term = {"id": "review-fixture-field", "name": "演坛", "description": "已审核场地效果。", "source": "审核暂译（官方公告机制）"}
        with tempfile.TemporaryDirectory() as folder:
            catalog = self.build(Path(folder), {
                "SKILL_DESCRIPTION_1001103": {"value": "附加演坛。解析值增加。", "reviewStatus": "approved"},
            }, terms={"1001103": [{**term, "sourceEvidence": {"rawHtmlPath": "E:\\private\\source.html"}}]})
            skill = next(s for s in catalog["skills"] if s["skillId"] == "1001103")
            self.assertIn(term, skill["statusTerms"])
            self.assertIn(term, catalog["statusTerms"])
            self.assertIn("审核暂译", skill["statusTermSources"])
            self.assertNotIn("E:\\private", json.dumps(catalog))


if __name__ == "__main__":
    unittest.main()
