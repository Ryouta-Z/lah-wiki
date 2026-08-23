import json
import tempfile
import unittest
from pathlib import Path

from scripts.lah_quickref import build_catalog, render_static_html


class LahQuickrefTest(unittest.TestCase):
    def _write_snapshot(self, directory: Path) -> None:
        (directory / "aliases.json").write_text(
            json.dumps({"阿卡西": "アカシ"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "ChineseSimplified-20260815.json").write_text(
            json.dumps(
                {
                    "CARD_NAME_AKASHI": "赤司",
                    "SKILL_NAME_1001101": "燃烧的白球",
                    "SKILL_DESCRIPTION_1001101": "对敌方单体造成70%伤害。",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (directory / "CardMaster-20260815").write_text(
            json.dumps(
                {
                    "100111": {
                        "heroCardId": 100111,
                        "cardName": "アカシ",
                        "resourceName": "akashi",
                        "rarity": 3,
                        "element": 1,
                        "role": 1,
                        "skillIds": [1001101],
                        "growths": [
                            {"level": 1, "hp": 404, "attack": 145, "agility": 98},
                            {"level": 60, "hp": 6066, "attack": 2185, "agility": 98},
                        ],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (directory / "SidekickMaster-20260815").write_text(
            json.dumps(
                {
                    "100111": {
                        "sidekickCardId": 100111,
                        "cardName": "アカシ",
                        "resourceName": "akashi",
                        "rarity": 4,
                        "role": 0,
                        "skillIds": [2001101],
                        "equipmentSkills": [3001101],
                        "growths": [
                            {"level": 1, "hp": 85, "attack": 42, "agility": 2},
                            {"level": 50, "hp": 340, "attack": 168, "agility": 2},
                        ],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (directory / "SkillMaster-20260815").write_text(
            json.dumps(
                {
                    "1001101": {
                        "skillId": 1001101,
                        "skillName": "燃ゆる白球",
                        "description": "日文英雄描述",
                    },
                    "2001101": {
                        "skillId": 2001101,
                        "skillName": "一球入魂",
                        "description": "日文助手主动描述",
                    },
                    "3001101": {
                        "skillId": 3001101,
                        "skillName": "装备技能",
                        "description": "日文装备描述",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_build_catalog_keeps_hero_and_sidekick_cards_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = build_catalog(source, source / "aliases.json")

        self.assertEqual(catalog["metadata"]["heroCardCount"], 1)
        self.assertEqual(catalog["metadata"]["sidekickCardCount"], 1)
        self.assertEqual([card["kind"] for card in catalog["cards"]], ["hero", "sidekick"])
        hero, sidekick = catalog["cards"]
        self.assertEqual(hero["name"], "赤司")
        self.assertEqual(hero["aliases"], ["阿卡西"])
        self.assertEqual(hero["element"]["label"], "火")
        self.assertEqual(hero["role"]["label"], "攻击")
        self.assertEqual(sidekick["role"]["label"], "无")
        self.assertEqual(hero["skills"][0]["name"], "燃烧的白球")
        self.assertEqual(sidekick["skills"][0]["relation"], "主动技能")
        self.assertEqual(sidekick["skills"][1]["relation"], "装备技能")

    def test_catalog_marks_untranslated_skills_as_japanese_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = build_catalog(source, source / "aliases.json")

        sidekick_skill = catalog["cards"][1]["skills"][0]
        self.assertEqual(sidekick_skill["nameSource"], "日文原文")
        self.assertEqual(sidekick_skill["descriptionSource"], "日文原文")

    def test_alias_lookup_returns_both_hero_and_sidekick_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = build_catalog(source, source / "aliases.json")

        matches = [card for card in catalog["cards"] if "阿卡西" in card["aliases"]]
        self.assertEqual({card["kind"] for card in matches}, {"hero", "sidekick"})

    def test_static_html_embeds_catalog_without_network_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            html = render_static_html(build_catalog(source, source / "aliases.json"))

        self.assertIn("赤司", html)
        self.assertIn("英雄", html)
        self.assertIn("助手", html)
        self.assertNotIn("fetch(", html)
        self.assertIn("...card.aliases", html)
        self.assertIn("join('\\n')", html)


if __name__ == "__main__":
    unittest.main()
