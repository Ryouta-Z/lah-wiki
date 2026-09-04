import json
import tempfile
import unittest
from pathlib import Path

from scripts.lah_quickref import (
    DEFAULT_SNAPSHOT_DIR,
    _avatar_for_card,
    _avatar_index,
    _index_by_id,
    _read_json,
    _snapshot_files,
    build_catalog,
    render_static_html,
)
from scripts.assistant_tags import default_assistant_tag_config, write_assistant_tag_config
from scripts.hero_tags import default_hero_tag_config, write_hero_tag_config


class LahQuickrefTest(unittest.TestCase):
    def _write_snapshot(self, directory: Path) -> None:
        (directory / "aliases.json").write_text(
            json.dumps({"阿卡西": "アカシ"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "char_map.json").write_text(
            json.dumps(
                {
                    "akashi": {"cn": "赤司", "jp": "アカシ"},
                    "missing": {"cn": "缺图角色", "jp": "欠損キャラ"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        icon_dir = directory / "icons"
        icon_dir.mkdir()
        (icon_dir / "akashi.png").write_bytes(b"fixture image")
        (directory / "ChineseSimplified-20260815.json").write_text(
            json.dumps(
                {
                    "CARD_NAME_AKASHI": "赤司",
                    "SKILL_NAME_1001101": "燃烧的白球",
                    "SKILL_DESCRIPTION_1001101": "对敌方附加逮捕、解析。解析值达到20时，发动“溢流光谱”和“好兴奋啊！”。",
                    "SKILL_DESCRIPTION_1001105": "官方强化基础说明",
                    "SKILL_EFFECT_CONDITION_DESCRIPTION_1001105_2": "官方唯一强化二",
                    "SKILL_EFFECT_CONDITION_DESCRIPTION_1001105_3": "官方最高强化一",
                    "SKILL_EFFECT_CONDITION_DESCRIPTION_1001105_5": "官方并列后者",
                    "SKILL_NAME_3001102": "装备技能Ⅱ",
                    "SKILL_DESCRIPTION_3001102": "对敌方附加共鸣。",
                    "OVERRIDE_STATUS_NAME_7003": "追加词条",
                    "OVERRIDE_STATUS_DESCRIPTION_7003": "追加效果说明。",
                    "OVERRIDE_STATUS_NAME_6692": "解析",
                    "OVERRIDE_STATUS_DESCRIPTION_6692": "从对手受到的伤害变为1.2倍。<br>容易被对手锁定。",
                    "OVERRIDE_STATUS_NAME_6707": "溢流光谱",
                    "OVERRIDE_STATUS_DESCRIPTION_6707": "对敌方随机目标造成3次50%伤害。<br>技能发动后，解析值变为0。",
                    "OVERRIDE_STATUS_NAME_5189": "好兴奋啊！",
                    "OVERRIDE_STATUS_DESCRIPTION_5189": "逮捕。逮捕后附加伤痕。逮捕。",
                    "OVERRIDE_STATUS_NAME_3409": "伤痕",
                    "OVERRIDE_STATUS_DESCRIPTION_3409": "第一种伤痕说明。",
                    "OVERRIDE_STATUS_NAME_4866": "伤痕",
                    "OVERRIDE_STATUS_DESCRIPTION_4866": "第二种伤痕说明。",
                    "STATUS_NAME_1001101": "逮捕",
                    "STATUS_DESCRIPTION_1001101": "自动行动时，变得容易被对手锁定。",
                    "OVERRIDE_STATUS_NAME_7001": "共鸣",
                    "OVERRIDE_STATUS_DESCRIPTION_7001": "第一种说明。",
                    "OVERRIDE_STATUS_NAME_7002": "共鸣",
                    "OVERRIDE_STATUS_DESCRIPTION_7002": "第二种说明。",
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
                        "hasSkillUpgrade": True,
                        "skillIds": [1001101, 1001104, 1001103],
                        "growths": [
                            {"level": 1, "hp": 404, "attack": 145, "agility": 98},
                            {"level": 60, "hp": 6066, "attack": 2185, "agility": 98},
                        ],
                        "skillProvider": {
                            "activeSkills": [
                                {"skillId": 1001101, "skillLearnNo": 1, "skillUpgrade": 0},
                                {"skillId": 1001104, "skillLearnNo": 2, "skillUpgrade": 0},
                                {"skillId": 1001103, "skillLearnNo": 3, "skillUpgrade": 0},
                                {"skillId": 1001105, "skillLearnNo": 4, "skillUpgrade": 1},
                                {"skillId": 1001106, "skillLearnNo": 5, "skillUpgrade": 1},
                                {"skillId": 1001107, "skillLearnNo": 6, "skillUpgrade": 1},
                            ]
                        },
                        "skillUpgradeQuestInfos": [
                            {"skillUpgrade": 1, "questId": 302008, "changeSkills": [{"beforeSkillId": 1001101, "afterSkillId": 1001105}]}
                        ],
                    }
                    ,
                    "100116": {
                        "heroCardId": 100116,
                        "cardName": "アカシ",
                        "resourceName": "akashi",
                        "rarity": 6,
                        "element": 1,
                        "role": 1,
                        "hasSkillUpgrade": True,
                        "skillIds": [1001101, 1001104, 1001103],
                        "growths": [
                            {"level": 1, "hp": 539, "attack": 145, "agility": 98},
                            {"level": 60, "hp": 8066, "attack": 2185, "agility": 98},
                        ],
                        "skillProvider": {
                            "activeSkills": [
                                {"skillId": 1001101, "skillLearnNo": 1, "skillUpgrade": 0},
                                {"skillId": 1001104, "skillLearnNo": 2, "skillUpgrade": 0},
                                {"skillId": 1001103, "skillLearnNo": 3, "skillUpgrade": 0},
                                {"skillId": 1001105, "skillLearnNo": 4, "skillUpgrade": 1},
                                {"skillId": 1001106, "skillLearnNo": 5, "skillUpgrade": 1},
                                {"skillId": 1001107, "skillLearnNo": 6, "skillUpgrade": 1},
                            ]
                        },
                    }
                    ,
                    "100121": {
                        "heroCardId": 100121,
                        "cardName": "酔虎のアカシ",
                        "resourceName": "akashiXmas",
                        "rarity": 5,
                        "element": 1,
                        "role": 1,
                        "skillIds": [1001101],
                        "growths": [{"level": 60, "hp": 5066, "attack": 2185, "agility": 98}],
                    },
                    "100122": {
                        "heroCardId": 100122,
                        "cardName": "酔虎のアカシ",
                        "resourceName": "akashiXmas",
                        "rarity": 6,
                        "element": 1,
                        "role": 1,
                        "skillIds": [1001101],
                        "growths": [{"level": 60, "hp": 6066, "attack": 2185, "agility": 98}],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (directory / "SidekickMaster-20260815").write_text(
            json.dumps(
                {
                    "100110": {
                        "sidekickCardId": 100110,
                        "stockId": 10011,
                        "cardName": "アカシ",
                        "resourceName": "akashi",
                        "rarity": 4,
                        "role": 0,
                        "levelZone": 1,
                        "skillIds": [2001101],
                        "equipmentSkills": [3001101],
                        "growths": [{"level": 1, "hp": 85, "attack": 42, "agility": 2}],
                    },
                    "100111": {
                        "sidekickCardId": 100111,
                        "stockId": 10011,
                        "cardName": "アカシ",
                        "resourceName": "akashi",
                        "rarity": 4,
                        "role": 0,
                        "levelZone": 6,
                        "skillIds": [2001101],
                        "equipmentSkills": [3001101, 3001102],
                        "equipmentAppendSkills": [8001102],
                        "growths": [
                            {"level": 1, "hp": 85, "attack": 42, "agility": 2},
                            {"level": 50, "hp": 340, "attack": 168, "agility": 2},
                        ],
                    },
                    "100211": {
                        "sidekickCardId": 100211,
                        "stockId": 10021,
                        "cardName": "重复助手",
                        "resourceName": "duplicate",
                        "rarity": 4,
                        "role": 0,
                        "levelZone": 6,
                        "skillIds": [2002101],
                        "equipmentSkills": [3002101],
                        "equipmentAppendSkills": [8002101],
                        "growths": [{"level": 50, "hp": 340, "attack": 168, "agility": 2}],
                    },
                    "100311": {
                        "sidekickCardId": 100311,
                        "stockId": 10031,
                        "cardName": "空白助手",
                        "resourceName": "empty",
                        "rarity": 4,
                        "role": 0,
                        "levelZone": 6,
                        "skillIds": [2003101],
                        "equipmentSkills": [3003101],
                        "equipmentAppendSkills": [8003101],
                        "growths": [{"level": 50, "hp": 340, "attack": 168, "agility": 2}],
                    },
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
                        "useView": 0,
                        "description": "日文英雄描述",
                        "effects": [{"skillEffectId": 6692}, {"skillEffectId": 6707}, {"skillEffectId": 5189}],
                    },
                    "2001101": {
                        "skillId": 2001101,
                        "skillName": "一球入魂",
                        "useView": 3500,
                        "description": "日文助手主动描述",
                    },
                    "3001101": {
                        "skillId": 3001101,
                        "skillName": "装备技能",
                        "useView": 9000,
                        "description": "日文装备描述",
                    },
                    "3001102": {
                        "skillId": 3001102,
                        "skillName": "装备技能Ⅱ",
                        "description": "日文装备最高描述",
                        "effects": [{"skillEffectId": 7001}, {"skillEffectId": 7002}],
                    },
                    "8001102": {
                        "skillId": 8001102,
                        "skillName": "追加装备效果",
                        "description": "追加词条。",
                        "effects": [{"skillEffectId": 7003}],
                    },
                    "2002101": {"skillId": 2002101, "skillName": "重复主动", "useView": 3500, "description": "主动描述"},
                    "3002101": {"skillId": 3002101, "skillName": "重复装备", "description": "重复说明"},
                    "8002101": {"skillId": 8002101, "skillName": "重复追加", "description": "重复说明"},
                    "2003101": {"skillId": 2003101, "skillName": "空白主动", "useView": 3500, "description": "主动描述"},
                    "3003101": {"skillId": 3003101, "skillName": "空白装备", "description": "主装备说明"},
                    "8003101": {"skillId": 8003101, "skillName": "空白追加", "description": ""},
                    "1001105": {
                        "skillId": 1001105,
                        "skillName": "燃ゆる白球+",
                        "description": "日文强化描述",
                        "effects": [
                            {
                                "serialNo": 1,
                                "conditionGroupId": 1,
                                "conditionPriority": 0,
                                "conditionDescription": "<style=\"改行\"></style>中间强化一",
                            },
                            {
                                "serialNo": 2,
                                "conditionGroupId": 2,
                                "conditionPriority": 0,
                                "conditionDescription": "<style=\"改行\"></style>唯一强化二",
                            },
                            {
                                "serialNo": 3,
                                "conditionGroupId": 1,
                                "conditionPriority": 2,
                                "conditionDescription": "<style=\"改行\"></style>最高强化一",
                            },
                            {
                                "serialNo": 4,
                                "conditionGroupId": 3,
                                "conditionPriority": 1,
                                "conditionDescription": "<style=\"改行\"></style>并列前者",
                            },
                            {
                                "serialNo": 5,
                                "conditionGroupId": 3,
                                "conditionPriority": 1,
                                "conditionDescription": "<style=\"改行\"></style>并列后者",
                            },
                        ],
                    },
                    "1001104": {"skillId": 1001104, "skillName": "第二技能", "useView": 2000, "description": "日文第二技能描述"},
                    "1001103": {"skillId": 1001103, "skillName": "第三技能", "useView": 16000, "description": "日文第三技能描述"},
                    "1001106": {"skillId": 1001106, "skillName": "第二技能+", "description": "日文第二技能强化描述"},
                    "1001107": {"skillId": 1001107, "skillName": "第三技能+", "description": "日文第三技能强化描述"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _catalog(self, source: Path, assistant_tags_path: Path | None = None, hero_tags_path: Path | None = None) -> dict:
        return build_catalog(
            source,
            source / "aliases.json",
            source / "char_map.json",
            source / "icons",
            assistant_tags_path=assistant_tags_path,
            hero_tags_path=hero_tags_path,
        )

    def test_build_catalog_keeps_hero_and_sidekick_cards_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        self.assertEqual(catalog["metadata"]["heroCardCount"], 2)
        self.assertEqual(catalog["metadata"]["sidekickCardCount"], 3)
        self.assertEqual(
            [card["kind"] for card in catalog["cards"]],
            ["hero", "hero", "sidekick", "sidekick", "sidekick"],
        )
        cards_by_id = {card["cardId"]: card for card in catalog["cards"]}
        hero = cards_by_id["100116"]
        holiday_hero = cards_by_id["100122"]
        sidekick = cards_by_id["100111"]
        self.assertEqual(hero["name"], "赤司")
        self.assertEqual(hero["cardId"], "100116")
        self.assertEqual(hero["rarity"], 6)
        self.assertEqual(hero["initialRarity"], 3)
        self.assertEqual(hero["aliases"], ["阿卡西"])
        self.assertEqual(hero["avatar"], {"status": "available", "code": "akashi"})
        self.assertEqual(hero["element"]["label"], "火")
        self.assertEqual(hero["role"]["label"], "攻击")
        self.assertIsNone(sidekick["element"])
        self.assertIsNone(sidekick["role"])
        self.assertEqual(hero["stats"]["level60"]["hp"], 8066)
        self.assertEqual(holiday_hero["rarity"], 6)
        self.assertEqual(holiday_hero["initialRarity"], 5)
        self.assertIsNone(sidekick["initialRarity"])
        self.assertNotIn("level1", hero["stats"])
        self.assertNotIn("max", hero["stats"])
        self.assertEqual(hero["skills"][0]["name"], "燃烧的白球")
        self.assertEqual([skill["viewCost"] for skill in hero["skills"]], [0, 2000, 16000])
        self.assertEqual(
            hero["skills"][0]["statusTerms"],
            [
                {"id": "6692", "name": "解析", "description": "从对手受到的伤害变为1.2倍。\n容易被对手锁定。", "source": "官方简中"},
                {"id": "6707", "name": "溢流光谱", "description": "对敌方随机目标造成3次50%伤害。\n技能发动后，解析值变为0。", "source": "官方简中"},
                {"id": "5189", "name": "好兴奋啊！", "description": "逮捕。逮捕后附加伤痕。逮捕。", "source": "官方简中"},
                {"id": "1001101", "name": "逮捕", "description": "自动行动时，变得容易被对手锁定。", "source": "官方简中"},
            ],
        )
        glossary_by_id = {term["id"]: term for term in catalog["statusTerms"]}
        self.assertEqual(glossary_by_id["1001101"]["name"], "逮捕")
        self.assertEqual(glossary_by_id["5189"]["name"], "好兴奋啊！")
        self.assertEqual(sidekick["skills"][0]["relation"], "主动技能（最高阶段）")
        self.assertEqual(sidekick["skills"][0]["viewCost"], 3500)
        self.assertEqual(sidekick["skills"][1]["relation"], "装备技能（最高等级）")
        self.assertEqual(sidekick["skills"][1]["skillId"], "3001102")
        self.assertIsNone(sidekick["skills"][1]["viewCost"])
        self.assertEqual(
            sidekick["skills"][1]["description"],
            "【装备效果】\n对敌方附加共鸣。\n\n【追加效果】\n追加词条。",
        )
        self.assertEqual(sidekick["skills"][1]["descriptionSource"], "部分日文回退")
        self.assertEqual(sidekick["skills"][1]["officialChineseAvailability"], "部分官方简中")
        self.assertEqual(sidekick["skills"][1]["statusTerms"], [
            {"id": "7003", "name": "追加词条", "description": "追加效果说明。", "source": "官方简中"},
        ])
        self.assertEqual(sidekick["skillLevel"], 6)
        self.assertEqual(catalog["skillUpgrades"][0]["before"]["skillId"], "1001101")
        self.assertEqual(catalog["skillUpgrades"][0]["after"]["skillId"], "1001105")
        self.assertEqual(catalog["skillUpgrades"][0]["before"]["description"], "对敌方附加逮捕、解析。解析值达到20时，发动“溢流光谱”和“好兴奋啊！”。")
        self.assertEqual(
            catalog["skillUpgrades"][0]["after"]["description"],
            "官方强化基础说明\n官方唯一强化二\n官方最高强化一\n官方并列后者",
        )
        self.assertEqual(catalog["skillUpgrades"][0]["after"]["descriptionSource"], "官方简中")
        self.assertEqual(catalog["skillUpgrades"][0]["after"]["officialChineseAvailability"], "完整官方简中")
        self.assertEqual(len(hero["skillUpgrades"]), 3)
        self.assertEqual(
            [upgrade["before"]["relation"] for upgrade in hero["skillUpgrades"]],
            ["技能 1", "技能 2", "技能 3"],
        )
        self.assertEqual(
            [(upgrade["before"]["skillId"], upgrade["after"]["skillId"]) for upgrade in hero["skillUpgrades"]],
            [("1001101", "1001105"), ("1001104", "1001106"), ("1001103", "1001107")],
        )
        self.assertEqual([upgrade["questId"] for upgrade in hero["skillUpgrades"]], ["302008"] * 3)

    def test_sidekick_equipment_appends_stay_in_one_skill_card(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        sidekicks = [card for card in catalog["cards"] if card["kind"] == "sidekick"]
        self.assertTrue(all(len(card["skills"]) == 2 for card in sidekicks))

        duplicate = next(card for card in sidekicks if card["cardId"] == "100211")["skills"][1]
        self.assertEqual(duplicate["description"], "重复说明")
        self.assertNotIn("追加效果", duplicate["description"])

        empty = next(card for card in sidekicks if card["cardId"] == "100311")["skills"][1]
        self.assertEqual(empty["description"], "主装备说明")
        self.assertNotIn("追加效果", empty["description"])

    def test_catalog_marks_untranslated_skills_as_japanese_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        sidekick_skill = next(card for card in catalog["cards"] if card["kind"] == "sidekick")["skills"][0]
        self.assertEqual(sidekick_skill["nameSource"], "日文原文")
        self.assertEqual(sidekick_skill["descriptionSource"], "日文原文")

    def test_catalog_embeds_public_assistant_tags_without_tagging_heroes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            tags_path = source / "assistant_tags.json"
            config = default_assistant_tag_config()
            config["assignments"] = {"sidekick:100111": ["target-self", "value-damage"]}
            config["pinnedAssignments"] = {"sidekick:100111": ["value-damage"]}
            write_assistant_tag_config(tags_path, config)
            catalog = self._catalog(source, tags_path)

        sidekick = next(card for card in catalog["cards"] if card["key"] == "sidekick:100111")
        hero = next(card for card in catalog["cards"] if card["key"] == "hero:100116")
        self.assertEqual(
            sidekick["tags"],
            [
                {"id": "target-self", "label": "自身", "path": ["作用目标", "自身"], "pinned": False},
                {"id": "value-damage", "label": "伤害", "path": ["作用数值", "伤害"], "pinned": True},
            ],
        )
        self.assertNotIn("tags", hero)
        self.assertEqual(len(catalog["assistantTags"]), 25)

    def test_catalog_embeds_independent_hero_tags_without_tagging_sidekicks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            tags_path = source / "hero_tags.json"
            config = default_hero_tag_config()
            config["tags"] = [
                {"id": "role", "label": "定位", "parentId": None},
                {"id": "attack", "label": "攻击", "parentId": "role"},
            ]
            config["assignments"] = {"hero:100116": ["attack"]}
            config["pinnedAssignments"] = {"hero:100116": ["attack"]}
            write_hero_tag_config(tags_path, config)
            catalog = self._catalog(source, hero_tags_path=tags_path)

        hero = next(card for card in catalog["cards"] if card["key"] == "hero:100116")
        sidekick = next(card for card in catalog["cards"] if card["key"] == "sidekick:100111")
        self.assertEqual(hero["tags"], [{"id": "attack", "label": "攻击", "path": ["定位", "攻击"], "pinned": True}])
        self.assertNotIn("tags", sidekick)
        self.assertEqual(catalog["heroTags"], config["tags"])
        self.assertEqual(catalog["assistantTags"], [])

    def test_official_snapshot_links_status_terms_for_heroes_sidekicks_and_upgrades(self):
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)
        direct_skills = [skill for card in catalog["cards"] for skill in card["skills"] if skill["statusTerms"]]
        direct_term_ids = {term["id"] for skill in direct_skills for term in skill["statusTerms"]}
        upgraded_heroes = [card for card in catalog["cards"] if card["kind"] == "hero" and card["skillUpgrades"]]

        self.assertEqual(len(direct_skills), 155)
        self.assertEqual(len(direct_term_ids), 135)
        sidekicks = [card for card in catalog["cards"] if card["kind"] == "sidekick"]
        self.assertEqual(len(sidekicks), 153)
        self.assertTrue(all(len(card["skills"]) == 2 for card in sidekicks))
        self.assertEqual(len(upgraded_heroes), 20)
        self.assertTrue(all(len(card["skillUpgrades"]) == 3 for card in upgraded_heroes))
        self.assertEqual(len(catalog["skillUpgrades"]), 60)

        snapshot = _snapshot_files(DEFAULT_SNAPSHOT_DIR)
        raw_cards = [
            *_read_json(snapshot["hero_cards"]).values(),
            *_read_json(snapshot["sidekick_cards"]).values(),
        ]
        active_ids = {str(skill_id) for card in raw_cards for skill_id in card.get("skillIds") or []}
        skills = _index_by_id(_read_json(snapshot["skills"]), "skillId")
        self.assertEqual(len(active_ids), 1159)
        self.assertTrue(all(isinstance(skills[skill_id].get("useView"), int) for skill_id in active_ids))

        hero = next(card for card in catalog["cards"] if card["key"] == "hero:123013")
        hero_skill = next(skill for skill in hero["skills"] if skill["name"] == "晴空航路+")
        self.assertEqual(
            hero_skill["statusTerms"],
            [{"id": "4739", "name": "爆破+", "description": "View基础值+1000。此效果视为与爆破同名的效果。", "source": "官方简中"}],
        )

        sidekick = next(card for card in catalog["cards"] if card["key"] == "sidekick:123016")
        sidekick_skill = next(skill for skill in sidekick["skills"] if skill["name"] == "航海士的气象观测VI")
        self.assertEqual(
            sidekick_skill["statusTerms"],
            [{"id": "4729", "name": "ATK+15%", "description": "ATK+15%。", "source": "官方简中"}],
        )

        kalaski = next(card for card in catalog["cards"] if card["cardId"] == "106422")
        limelight = next(skill for skill in kalaski["skills"] if skill["skillId"] == "1064201")
        highlights = next(skill for skill in kalaski["skills"] if skill["skillId"] == "1064202")
        spotlight = {
            "id": "1064204",
            "name": "聚光",
            "description": "自身以及定位为“获得View”的我方，ATK上升各自View的40%。最少上升500，最多上升至3000。此效果不重复。",
            "source": "官方简中",
        }
        self.assertIn(spotlight, limelight["statusTerms"])
        self.assertIn(spotlight, highlights["statusTerms"])

        kouki = next(card for card in catalog["cards"] if card["cardId"] == "101812")
        kouki_upgrade = next(upgrade for upgrade in kouki["skillUpgrades"] if upgrade["after"]["skillId"] == "1018105")
        self.assertEqual(kouki_upgrade["after"]["descriptionSource"], "官方简中")
        self.assertEqual(kouki_upgrade["after"]["officialChineseAvailability"], "完整官方简中")
        self.assertIn("附加1次行动期间ATK下降。", kouki_upgrade["after"]["description"])
        self.assertIn("获得3000View。", kouki_upgrade["after"]["description"])
        self.assertIn("所受伤害随ViewPower减少", kouki_upgrade["after"]["description"])

        garmr = next(card for card in catalog["cards"] if card["name"] == "格米萨")
        upgraded_skill = next(
            skill
            for upgrade in garmr["skillUpgrades"]
            for skill in (upgrade["before"], upgrade["after"])
            if skill["name"] == "太阳之舞+"
        )
        self.assertEqual(upgraded_skill["descriptionSource"], "官方简中")
        self.assertEqual(
            upgraded_skill["statusTerms"],
            [{
                "id": "special:sunlight",
                "name": "阳光",
                "description": "ATK+20%。",
                "inlineDescription": "ATK+20%",
                "source": "官方简中",
            }],
        )

    def test_highest_upgrade_uses_official_conditions_and_removes_subsumed_effects(self):
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)

        rakta = next(card for card in catalog["cards"] if card["cardId"] == "102014")
        rakta_after = next(upgrade["after"] for upgrade in rakta["skillUpgrades"] if upgrade["after"]["skillId"] == "1020107")
        self.assertEqual(rakta_after["descriptionSource"], "官方简中")
        self.assertIn("解除所有减益效果。", rakta_after["description"])
        self.assertNotIn("解除3个减益效果", rakta_after["description"])
        self.assertIn("恢复目标基础ATK100%的HP。", rakta_after["description"])

        suhail = next(card for card in catalog["cards"] if card["cardId"] == "103012")
        suhail_after = next(upgrade["after"] for upgrade in suhail["skillUpgrades"] if upgrade["after"]["skillId"] == "1030107")
        self.assertEqual(suhail_after["descriptionSource"], "部分日文回退")
        self.assertTrue(suhail_after["description"].startswith("发动前，解除自身2个减益效果。"))
        self.assertIn("对敌方全体造成100%伤害", suhail_after["description"])

    def test_borealis_upgrades_and_special_terms_have_auditable_sources(self):
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)
        borealis = next(card for card in catalog["cards"] if card["cardId"] == "108213")
        after_skills = [upgrade["after"] for upgrade in borealis["skillUpgrades"]]
        self.assertTrue(all(skill["descriptionSource"] == "官方简中" for skill in after_skills))
        self.assertTrue(all(skill["officialChineseAvailability"] == "完整官方简中" for skill in after_skills))
        first = next(skill for skill in after_skills if skill["skillId"] == "1082105")
        self.assertIn("交响槽", first["description"])
        self.assertIn("三重颂歌", first["description"])
        concert = next(skill for skill in after_skills if skill["skillId"] == "1082106")["statusTerms"]
        self.assertEqual(concert[0]["name"], "协奏")
        self.assertEqual(concert[0]["source"], "官方简中")

        santesu = next(card for card in catalog["cards"] if card["cardId"] == "111222")
        third_skill = next(skill for skill in santesu["skills"] if skill["skillId"] == "1112204")
        special_terms = {term["id"]: term for term in third_skill["statusTerms"]}
        self.assertEqual(special_terms["special:mirror-realm"]["matchName"], "鏡界")
        self.assertEqual(special_terms["special:second-arrow"]["matchName"], "マーショディク・ニール")
        self.assertEqual(special_terms["special:second-arrow"]["source"], "专用说明")

        fallback_upgrades = [upgrade["after"] for upgrade in catalog["skillUpgrades"] if upgrade["after"]["descriptionSource"] != "官方简中"]
        self.assertTrue(all(skill["officialChineseAvailability"] != "完整官方简中" for skill in fallback_upgrades))

    def test_alias_lookup_returns_both_hero_and_sidekick_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        matches = [card for card in catalog["cards"] if "阿卡西" in card["aliases"]]
        self.assertEqual({card["kind"] for card in matches}, {"hero", "sidekick"})

    def test_static_html_embeds_catalog_without_network_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            html = render_static_html(
                self._catalog(source),
                local_official_asset_prefix="../data/cache/official-ui-candidates/selected",
                use_official_card_layout=True,
            )
            public_html = render_static_html(self._catalog(source), include_tag_settings=False)

        self.assertIn("赤司", html)
        self.assertIn("英雄", html)
        self.assertIn("助手", html)
        self.assertIn("技能强化", html)
        self.assertIn("const skillCostMarkup = skill => skill.viewCost != null", html)
        self.assertIn("skillCostMarkup(skill)", html)
        self.assertIn("强化后（最高等级）", html)
        self.assertIn("【装备效果】", html)
        self.assertIn("【追加效果】", html)
        self.assertNotIn("fetch(", html)
        self.assertIn("...card.aliases", html)
        self.assertIn("join('\\n')", html)
        self.assertIn("avatarMarkup", html)
        self.assertIn("avatar-image", html)
        self.assertIn("function heroMetadataMarkup", html)
        self.assertIn("function useHeroElementFallback", html)
        self.assertIn("hero-role", html)
        self.assertIn('const localOfficialAssetPrefix = "../data/cache/official-ui-candidates/selected"', html)
        self.assertIn("const useOfficialCardLayout = true", html)
        self.assertIn("const useOfficialCardLayout = false", public_html)
        self.assertIn('<body class="official-card-layout">', html)
        self.assertIn('<body class="">', public_html)
        self.assertIn("const sidekickTags = card.tags || [];", html)
        self.assertIn("const orderedSidekickTags = [...sidekickTags.filter(tag => tag.pinned), ...sidekickTags.filter(tag => !tag.pinned)];", html)
        self.assertIn("orderedSidekickTags.slice(0, 3)", html)
        self.assertIn("orderedSidekickTags.length - 3", html)
        self.assertIn("const legacyTags = card.kind === 'hero'", html)
        self.assertIn("function characterPortraitMarkup", html)
        self.assertIn("function cardFrameMarkup", html)
        self.assertIn("hero-frame-${frame}.png", html)
        self.assertIn("role-${role}-wordmark.png", html)
        self.assertIn("body.official-card-layout .results { grid-template-columns: repeat(4, minmax(0, 1fr));", html)
        self.assertIn("body.official-card-layout .card-layout { grid-template-columns: 116px minmax(0, 1fr);", html)
        self.assertIn("grid-template-columns: repeat(auto-fill, minmax(230px, 1fr))", public_html)
        self.assertIn("const stats = card.kind === 'hero'\n        ?", html)
        self.assertIn('class="hero-detail-header"', html)
        self.assertIn('class="close detail-close"', html)
        self.assertIn('width: calc(100% + 48px)', html)
        self.assertIn('hero-detail-header .detail-close', html)
        self.assertIn("button.detail-close", html)
        self.assertIn("position: sticky; top: 0", html)
        self.assertIn('<div class="muted">属性</div>', html)
        self.assertIn('<div class="muted">职能</div>', html)
        self.assertIn("? [['60级 HP',card.stats.level60.hp]", html)
        self.assertIn(
            ": [['稀有度','★'.repeat(card.rarity)], ['满级 HP',card.stats.max.hp], ['满级 攻击',card.stats.max.attack], ['满级 速度',card.stats.max.agility]];",
            html,
        )
        self.assertNotIn("['1级 HP',card.stats.level1.hp]", html)
        self.assertNotIn("? [['稀有度','★'.repeat(card.rarity)]", html)
        self.assertNotIn("const heroStats =", html)
        self.assertNotIn("const sidekickStats =", html)
        self.assertIn('id="sortField"', html)
        self.assertIn('id="sortDirection"', html)
        self.assertIn('class="filter-control"', html)
        self.assertIn('<span class="control-label">分类</span>', html)
        self.assertIn('<span class="control-label" id="rarity-label">稀有度</span>', html)
        self.assertIn('<span class="control-label" id="element-label">属性</span>', html)
        self.assertIn('<span class="control-label" id="role-label">职能</span>', html)
        self.assertIn('class="filter-control sort-control"', html)
        self.assertIn('<select id="kind"><option value="">全角色</option>', html)
        self.assertIn('class="filter-control multi-select" id="rarity"', html)
        self.assertIn('class="filter-control multi-select" id="element"', html)
        self.assertIn('class="filter-control multi-select" id="role"', html)
        self.assertIn('class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false"', html)
        self.assertIn('class="multi-select-menu" id="rarity-menu" role="group"', html)
        self.assertIn('class="multi-select-clear" type="button">清空</button>', html)
        self.assertIn("white-space: nowrap", html)
        self.assertIn("font-size: 14px", html)
        self.assertIn("padding: 9px", html)
        self.assertNotIn('<select id="rarity">', html)
        self.assertNotIn('<select id="element">', html)
        self.assertNotIn('<select id="role">', html)
        self.assertIn("card.kind === 'hero' ?", html)
        self.assertNotIn("'无元素'", html)
        self.assertIn("const heroes = cards.filter(card => card.kind === 'hero');", html)
        self.assertIn("setupMultiSelect('rarity', new Set(cards.map(card => '★'.repeat(displayRarity(card)))));", html)
        self.assertIn("setupMultiSelect('element', new Set(heroes.map(card => card.element?.label)));", html)
        self.assertIn("setupMultiSelect('role', new Set(heroes.map(card => card.role?.label)));", html)
        self.assertIn("function selectedValues(id)", html)
        self.assertIn("!rarity.size || rarity.has('★'.repeat(displayRarity(card)))", html)
        self.assertIn("!element.size || element.has(card.element?.label)", html)
        self.assertIn("!role.size || role.has(card.role?.label)", html)
        self.assertIn("menu.hidden = !menu.hidden", html)
        self.assertIn("if (!event.target.closest('.multi-select'))", html)
        self.assertIn('id="hero-tags"', html)
        self.assertIn('id="assistant-tags"', html)
        self.assertIn("const assistantTags = catalog.assistantTags || [];", html)
        self.assertIn("const heroTags = catalog.heroTags || [];", html)
        self.assertIn("function setupTagSelector(id, tags)", html)
        self.assertIn("const selectedHeroTagIds = setupTagSelector('hero-tags', heroTags);", html)
        self.assertIn("const selectedAssistantTagIds = setupTagSelector('assistant-tags', assistantTags);", html)
        self.assertIn("menuPath = []", html)
        self.assertIn("branch.addEventListener('mouseenter', open)", html)
        self.assertIn("branch.addEventListener('focus', open)", html)
        self.assertIn("if (event.type === 'click') event.stopPropagation();", html)
        self.assertIn(".tag-select .multi-select-options", html)
        self.assertIn(".tag-menu-level .tag-menu-level", html)
        self.assertIn("tag.path.join(' › ')", html)
        self.assertIn("const tags = card.kind === 'hero' ? selectedHeroTagIds : selectedAssistantTagIds;", html)
        self.assertIn("[...tags].every(tagId => card.tags?.some(tag => tag.id === tagId))", html)
        self.assertIn("...(card.tags || []).map(tag => tag.label)", html)
        self.assertIn("...orderedSidekickTags.slice(0, 3).map(tag => tag.label)", html)
        self.assertNotIn("['元素',card.element?.label", html)
        self.assertNotIn("['定位',card.role", html)
        self.assertIn("function compareCards(left, right)", html)
        self.assertIn("const numericFields = new Set(['cardId', 'rarity', 'hp', 'attack', 'agility']);", html)
        self.assertIn("const stats = card.kind === 'hero' ? card.stats.level60 : card.stats.max;", html)
        self.assertIn("if (leftValue == null && rightValue != null) return 1;", html)
        self.assertIn("if (leftValue != null && rightValue == null) return -1;", html)
        self.assertIn("return Number(left.cardId) - Number(right.cardId);", html)
        self.assertIn('id="statusDetail"', html)
        self.assertIn('button class="status-term"', html)
        self.assertIn("data-status-id", html)
        self.assertIn("function showStatusDetail", html)
        self.assertIn("const statusById = new Map(catalog.statusTerms.map", html)
        self.assertIn("function termMarkup", html)
        self.assertIn('class="status-term-highlight"', html)
        self.assertIn('class="status-term-note"', html)
        self.assertIn("status.inlineDescription", html)
        self.assertIn("item.matchName || item.name", html)
        self.assertIn("!seenNames.has(candidate.name)", html)
        self.assertIn("function statusDescriptionMarkup", html)
        self.assertIn("$('statusDetail').hidden = false;", html)
        self.assertIn("if (event.key !== 'Escape') return;", html)
        self.assertIn("const openControl = [...document.querySelectorAll('.multi-select')].find", html)
        self.assertIn("if (!$('statusDetail').hidden)", html)
        self.assertIn("const displayRarity = card => card.kind === 'hero' ? card.initialRarity : card.rarity;", html)
        self.assertIn("★'.repeat(displayRarity(card))", html)
        self.assertIn("${escape(kindLabel(card.kind))}", html)
        self.assertNotIn("技能 ${card.skills.length}", html)
        self.assertIn('id="tagSettings"', html)
        self.assertIn('id="tagSettingsDetail"', html)
        self.assertIn("http://127.0.0.1:8787/", html)
        self.assertIn("scripts/tag_admin.py", html)

    def test_avatar_mapping_uses_exact_japanese_then_chinese_and_never_guesses(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            char_map = json.loads((source / "char_map.json").read_text(encoding="utf-8"))
            index = _avatar_index(char_map, source / "icons")

        self.assertEqual(_avatar_for_card("akashi", "アカシ", "其他名称", index), {"status": "available", "code": "akashi"})
        self.assertEqual(_avatar_for_card("", "⇌アカシ", "⇌赤司", index), {"status": "available", "code": "akashi"})
        self.assertEqual(_avatar_for_card("", "不匹配", "赤司", index), {"status": "available", "code": "akashi"})
        self.assertEqual(_avatar_for_card("missing", "欠損キャラ", "缺图角色", index), {"status": "missing", "code": "missing"})
        self.assertEqual(_avatar_for_card("", "不存在", "不存在", index), {"status": "missing", "code": None})


if __name__ == "__main__":
    unittest.main()
