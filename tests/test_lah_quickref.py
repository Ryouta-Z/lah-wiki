import json
import tempfile
import unittest
from pathlib import Path

from scripts.lah_quickref import (
    DEFAULT_SNAPSHOT_DIR,
    _avatar_for_card,
    _avatar_index,
    build_catalog,
    render_static_html,
)


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
                    "SKILL_NAME_3001102": "装备技能Ⅱ",
                    "SKILL_DESCRIPTION_3001102": "对敌方附加共鸣。",
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
                        "skillIds": [1001101],
                        "growths": [
                            {"level": 1, "hp": 404, "attack": 145, "agility": 98},
                            {"level": 60, "hp": 6066, "attack": 2185, "agility": 98},
                        ],
                        "skillProvider": {"activeSkills": [{"skillId": 1001101, "skillLearnNo": 1}]},
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
                        "skillIds": [1001101],
                        "growths": [
                            {"level": 1, "hp": 539, "attack": 145, "agility": 98},
                            {"level": 60, "hp": 8066, "attack": 2185, "agility": 98},
                        ],
                        "skillProvider": {"activeSkills": [{"skillId": 1001101, "skillLearnNo": 1}]},
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
                        "effects": [{"skillEffectId": 6692}, {"skillEffectId": 6707}, {"skillEffectId": 5189}],
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
                    "3001102": {
                        "skillId": 3001102,
                        "skillName": "装备技能Ⅱ",
                        "description": "日文装备最高描述",
                        "effects": [{"skillEffectId": 7001}, {"skillEffectId": 7002}],
                    },
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
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _catalog(self, source: Path) -> dict:
        return build_catalog(
            source,
            source / "aliases.json",
            source / "char_map.json",
            source / "icons",
        )

    def test_build_catalog_keeps_hero_and_sidekick_cards_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        self.assertEqual(catalog["metadata"]["heroCardCount"], 2)
        self.assertEqual(catalog["metadata"]["sidekickCardCount"], 1)
        self.assertEqual([card["kind"] for card in catalog["cards"]], ["hero", "hero", "sidekick"])
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
        self.assertEqual(
            hero["skills"][0]["statusTerms"],
            [
                {"id": "6692", "name": "解析", "description": "从对手受到的伤害变为1.2倍。\n容易被对手锁定。"},
                {"id": "6707", "name": "溢流光谱", "description": "对敌方随机目标造成3次50%伤害。\n技能发动后，解析值变为0。"},
                {"id": "5189", "name": "好兴奋啊！", "description": "逮捕。逮捕后附加伤痕。逮捕。"},
                {"id": "1001101", "name": "逮捕", "description": "自动行动时，变得容易被对手锁定。"},
            ],
        )
        glossary_by_id = {term["id"]: term for term in catalog["statusTerms"]}
        self.assertEqual(glossary_by_id["1001101"]["name"], "逮捕")
        self.assertEqual(glossary_by_id["5189"]["name"], "好兴奋啊！")
        self.assertEqual(sidekick["skills"][0]["relation"], "主动技能（最高阶段）")
        self.assertEqual(sidekick["skills"][1]["relation"], "装备技能（最高等级）")
        self.assertEqual(sidekick["skills"][1]["skillId"], "3001102")
        self.assertEqual(sidekick["skills"][1]["statusTerms"], [])
        self.assertEqual(sidekick["skillLevel"], 6)
        self.assertEqual(catalog["skillUpgrades"][0]["before"]["skillId"], "1001101")
        self.assertEqual(catalog["skillUpgrades"][0]["after"]["skillId"], "1001105")
        self.assertEqual(catalog["skillUpgrades"][0]["before"]["description"], "对敌方附加逮捕、解析。解析值达到20时，发动“溢流光谱”和“好兴奋啊！”。")
        self.assertEqual(
            catalog["skillUpgrades"][0]["after"]["description"],
            "日文强化描述\n唯一强化二\n最高强化一\n并列后者",
        )
        self.assertEqual(catalog["skillUpgrades"][0]["after"]["descriptionSource"], "日文原文")

    def test_catalog_marks_untranslated_skills_as_japanese_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            self._write_snapshot(source)
            catalog = self._catalog(source)

        sidekick_skill = next(card for card in catalog["cards"] if card["kind"] == "sidekick")["skills"][0]
        self.assertEqual(sidekick_skill["nameSource"], "日文原文")
        self.assertEqual(sidekick_skill["descriptionSource"], "日文原文")

    def test_official_snapshot_links_status_terms_for_heroes_sidekicks_and_upgrades(self):
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)
        direct_skills = [skill for card in catalog["cards"] for skill in card["skills"] if skill["statusTerms"]]
        direct_term_ids = {term["id"] for skill in direct_skills for term in skill["statusTerms"]}

        self.assertEqual(len(direct_skills), 137)
        self.assertEqual(len(direct_term_ids), 117)

        hero = next(card for card in catalog["cards"] if card["key"] == "hero:123013")
        hero_skill = next(skill for skill in hero["skills"] if skill["name"] == "晴空航路+")
        self.assertEqual(
            hero_skill["statusTerms"],
            [{"id": "4739", "name": "爆破+", "description": "View基础值+1000。此效果视为与爆破同名的效果。"}],
        )

        sidekick = next(card for card in catalog["cards"] if card["key"] == "sidekick:123016")
        sidekick_skill = next(skill for skill in sidekick["skills"] if skill["name"] == "航海士的气象观测VI")
        self.assertEqual(
            sidekick_skill["statusTerms"],
            [{"id": "4729", "name": "ATK+15%", "description": "ATK+15%。"}],
        )

        kouki = next(card for card in catalog["cards"] if card["cardId"] == "101812")
        kouki_upgrade = next(upgrade for upgrade in kouki["skillUpgrades"] if upgrade["after"]["skillId"] == "1018105")
        self.assertEqual(kouki_upgrade["after"]["descriptionSource"], "日文原文")
        self.assertIn("1回の行動の間ATKダウンを付与。", kouki_upgrade["after"]["description"])
        self.assertIn("Viewを3000獲得。", kouki_upgrade["after"]["description"])
        self.assertIn("被ダメージ減少", kouki_upgrade["after"]["description"])
        self.assertNotIn("50%の確率", kouki_upgrade["after"]["description"])
        self.assertNotIn("65%の確率", kouki_upgrade["after"]["description"])
        self.assertNotIn("80%の確率", kouki_upgrade["after"]["description"])

        garmr = next(card for card in catalog["cards"] if card["name"] == "格米萨")
        upgraded_skill = next(
            skill
            for upgrade in garmr["skillUpgrades"]
            for skill in (upgrade["before"], upgrade["after"])
            if skill["name"] == "太阳之舞+"
        )
        self.assertEqual(upgraded_skill["descriptionSource"], "日文原文")
        self.assertEqual(upgraded_skill["statusTerms"], [])

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
            html = render_static_html(self._catalog(source))

        self.assertIn("赤司", html)
        self.assertIn("英雄", html)
        self.assertIn("助手", html)
        self.assertIn("技能强化", html)
        self.assertIn("强化后（最高等级）", html)
        self.assertNotIn("fetch(", html)
        self.assertIn("...card.aliases", html)
        self.assertIn("join('\\n')", html)
        self.assertIn("avatarMarkup", html)
        self.assertIn("avatar-image", html)
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
        self.assertIn("card.kind === 'hero' ? [card.element?.label, card.role?.label, kindLabel(card.kind)] : [kindLabel(card.kind)]", html)
        self.assertNotIn("['元素',card.element?.label", html)
        self.assertNotIn("['定位',card.role", html)
        self.assertIn("英雄卡固定展示属性、职能和类型；助手卡仅展示类型。", html)
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
        self.assertIn("自定义标签即将开放", html)

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
