import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from scripts.fetch_lah import _build_skills, _machine_translate
from scripts.official_lah import load_official_texts, load_snapshot_masters
from scripts.official_lah import OfficialTexts


class OfficialLahTextsTest(unittest.TestCase):
    def test_loads_card_and_skill_texts_by_master_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "ChineseSimplified-20260815.json").write_text(
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
            (source / "CardMaster-20260815").write_text(
                json.dumps({"100111": {"heroCardId": 100111, "resourceName": "akashi"}}),
                encoding="utf-8",
            )
            (source / "SkillMaster-20260815").write_text(
                json.dumps({"1001101": {"skillId": 1001101}}),
                encoding="utf-8",
            )

            texts = load_official_texts(source)
            masters = load_snapshot_masters(source)

        self.assertEqual(texts.card_name("100111"), "赤司")
        self.assertEqual(
            texts.skill_text("1001101"),
            ("燃烧的白球", "对敌方单体造成70%伤害。"),
        )
        self.assertEqual(masters[0]["100111"]["resourceName"], "akashi")
        self.assertEqual(masters[1]["1001101"]["skillId"], 1001101)

    def test_returns_empty_texts_when_the_snapshot_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            texts = load_official_texts(Path(directory))

        self.assertIsNone(texts.card_name("100111"))
        self.assertIsNone(texts.skill_text("1001101"))
        self.assertIsNone(load_snapshot_masters(Path(directory)))

    def test_rejects_snapshot_parts_with_different_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "ChineseSimplified-20260816.json").write_text(
                json.dumps({"CARD_NAME_AKASHI": "赤司"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (source / "CardMaster-20260815").write_text(
                json.dumps({"100111": {"heroCardId": 100111, "resourceName": "akashi"}}),
                encoding="utf-8",
            )
            (source / "SkillMaster-20260815").write_text("{}", encoding="utf-8")

            texts = load_official_texts(source)

        self.assertIsNone(texts.card_name("100111"))

    def test_official_skill_text_takes_priority_over_community_translation(self):
        entries = {}
        skills = {
            "1001101": {
                "skillId": 1001101,
                "skillName": "燃ゆる白球",
                "description": "日文描述",
                "isHeroSkill": True,
            }
        }
        official = OfficialTexts(
            card_names={},
            skill_texts={"1001101": ("燃烧的白球", "官方中文描述")},
        )
        community = {"1001101": ("社区名称", "社区中文描述")}

        _build_skills(entries, skills, community, official, mtl_map={})

        self.assertEqual(entries["skill:1001101"]["name"], "燃烧的白球")
        self.assertEqual(entries["skill:1001101"]["content"], "官方中文描述")

    def test_machine_translation_failure_keeps_cached_translations(self):
        class FailingTranslator:
            cache = {"缓存命中的日文": "缓存中的中文"}

            def translate_all(self, _texts):
                raise RuntimeError("translation unavailable")

        skills = {
            "1": {"description": "缓存命中的日文"},
            "2": {"description": "缓存未命中的日文"},
        }
        with patch("mtl.Translator", return_value=FailingTranslator()):
            translations = _machine_translate(skills, {}, OfficialTexts({}, {}))

        self.assertEqual(translations, {"缓存命中的日文": "缓存中的中文"})

    def test_machine_translation_http_failure_keeps_cached_translations(self):
        class FailingTranslator:
            cache = {"缓存命中的日文": "缓存中的中文"}

            def translate_all(self, _texts):
                raise httpx.ConnectError("translation unavailable")

        with patch("mtl.Translator", return_value=FailingTranslator()):
            translations = _machine_translate(
                {"1": {"description": "缓存命中的日文"}}, {}, OfficialTexts({}, {})
            )

        self.assertEqual(translations, {"缓存命中的日文": "缓存中的中文"})


if __name__ == "__main__":
    unittest.main()
