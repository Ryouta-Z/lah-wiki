import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts import assistant_tag_admin
from scripts.hero_tags import (
    delete_tag,
    default_hero_tag_config,
    reorder_tag_siblings,
    validate_hero_tag_config,
    write_hero_tag_config,
)


class HeroTagTest(unittest.TestCase):
    def test_empty_config_and_hero_key_validation(self):
        self.assertEqual(default_hero_tag_config(), {"version": 1, "tags": [], "assignments": {}, "pinnedAssignments": {}})
        config = {"version": 1, "tags": [{"id": "role", "label": "定位", "parentId": None}, {"id": "attack", "label": "攻击", "parentId": "role"}], "assignments": {"hero:100111": ["attack"]}, "pinnedAssignments": {"hero:100111": ["attack"]}}
        self.assertEqual(validate_hero_tag_config(config, {"hero:100111"})["assignments"], {"hero:100111": ["attack"]})
        with self.assertRaisesRegex(ValueError, "英雄键"):
            validate_hero_tag_config({**config, "assignments": {"sidekick:100111": ["attack"]}}, {"hero:100111"})
        with self.assertRaisesRegex(ValueError, "叶子"):
            validate_hero_tag_config({**config, "assignments": {"hero:100111": ["role"]}}, {"hero:100111"})

    def test_hero_sorting_pins_and_deletion_follow_the_shared_rules(self):
        config = {
            "version": 1,
            "tags": [
                {"id": "first", "label": "第一", "parentId": None},
                {"id": "second", "label": "第二", "parentId": None},
                {"id": "third", "label": "第三", "parentId": None},
                {"id": "fourth", "label": "第四", "parentId": None},
            ],
            "assignments": {"hero:100111": ["first", "second", "third", "fourth"]},
            "pinnedAssignments": {"hero:100111": ["first", "second", "third"]},
        }
        reorder_tag_siblings(config, None, ["fourth", "third", "second", "first"])
        self.assertEqual([tag["id"] for tag in config["tags"]], ["fourth", "third", "second", "first"])
        with self.assertRaisesRegex(ValueError, "最多置顶"):
            validate_hero_tag_config({**config, "pinnedAssignments": {"hero:100111": ["first", "second", "third", "fourth"]}}, {"hero:100111"})
        delete_tag(config, "second")
        self.assertEqual(config["assignments"], {"hero:100111": ["first", "third", "fourth"]})
        self.assertEqual(config["pinnedAssignments"], {"hero:100111": ["first", "third"]})

    def test_default_page_is_hero_and_modes_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hero_path, assistant_path, catalog_path = root / "hero_tags.json", root / "assistant_tags.json", root / "catalog.json"
            write_hero_tag_config(hero_path, default_hero_tag_config())
            catalog_path.write_text(json.dumps({"cards": [
                {"key": "hero:100111", "kind": "hero", "cardId": "100111", "name": "测试英雄", "originalName": "ヒーロー", "rarity": 4, "skills": [{"relation": "主动技能", "name": "测试", "description": "说明"}], "skillUpgrades": [{"before": {"name": "前", "description": "前说明"}, "after": {"name": "后", "description": "后说明"}}]},
                {"key": "sidekick:100111", "kind": "sidekick", "cardId": "100111", "name": "测试助手", "originalName": "サイド", "rarity": 4, "skills": [], "skillUpgrades": []},
            ]}, ensure_ascii=False), encoding="utf-8")
            with patch.multiple(assistant_tag_admin, DEFAULT_HERO_TAGS_PATH=hero_path, DEFAULT_ASSISTANT_TAGS_PATH=assistant_path, DEFAULT_CATALOG_PATH=catalog_path, rebuild_quickref=lambda: None):
                client = TestClient(assistant_tag_admin.create_app())
                page = client.get("/")
                self.assertIn("英雄标签管理", page.text)
                self.assertIn("let mode = 'hero'", page.text)
                self.assertIn("技能强化", page.text)
                self.assertEqual(client.get("/api/hero/state").json()["cards"][0]["key"], "hero:100111")
                self.assertEqual(client.get("/api/assistant/state").json()["cards"][0]["key"], "sidekick:100111")
                client.post("/api/hero/tags", json={"id": "attack", "label": "攻击", "parentId": None})
                saved = client.put("/api/hero/cards/hero:100111/tags", json={"tagIds": ["attack"], "pinnedTagIds": ["attack"]})
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(client.get("/api/assistant/state").json()["config"]["assignments"], {})


if __name__ == "__main__":
    unittest.main()
