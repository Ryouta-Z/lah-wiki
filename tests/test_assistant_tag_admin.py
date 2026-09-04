import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts import assistant_tag_admin
from scripts.assistant_tags import default_assistant_tag_config, write_assistant_tag_config


class AssistantTagAdminTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.tags_path = root / "assistant_tags.json"
        self.catalog_path = root / "quickref_catalog.json"
        write_assistant_tag_config(self.tags_path, default_assistant_tag_config())
        self.catalog_path.write_text(
            json.dumps(
                {
                    "cards": [
                        {
                            "key": "sidekick:100111",
                            "kind": "sidekick",
                            "cardId": "100111",
                            "name": "测试助手",
                            "originalName": "テスト",
                            "rarity": 4,
                            "skills": [{"relation": "主动技能", "name": "测试技能", "description": "测试说明"}],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.path_patch = patch.multiple(
            assistant_tag_admin,
            DEFAULT_ASSISTANT_TAGS_PATH=self.tags_path,
            DEFAULT_CATALOG_PATH=self.catalog_path,
            rebuild_quickref=lambda: None,
        )
        self.path_patch.start()
        self.client = TestClient(assistant_tag_admin.create_app())

    def tearDown(self):
        self.path_patch.stop()
        self.directory.cleanup()

    def test_local_admin_page_exposes_state_and_saves_leaf_assignments(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("仅本机可访问", page.text)
        self.assertIn("无法连接本机管理服务", page.text)
        self.assertIn("tag-popup", page.text)
        self.assertIn("activeMenuPath", page.text)
        self.assertIn("document.onkeydown", page.text)
        self.assertNotIn("tag-group", page.text)
        self.assertIn("countLabel", page.text)
        self.assertIn("assignmentDraftTagIds", page.text)
        self.assertIn("assignmentDraftPinnedTagIds", page.text)
        self.assertIn('id="pinnedTags"', page.text)
        self.assertIn("置顶标签（0/3）", page.text)
        self.assertIn("drag-handle", page.text)
        self.assertIn("/api/${mode}/tags/order", page.text)
        self.assertIn("depth === 0 ? 'below' : 'side'", page.text)
        self.assertIn("const menuGap = 16", page.text)
        self.assertIn("window.innerWidth", page.text)
        self.assertIn("tag-option-label", page.text)
        self.assertIn("height: 22px", page.text)
        self.assertIn("input.click()", page.text)
        self.assertIn("if (!children(tag.id).length)", page.text)

        state = self.client.get("/api/assistant/state")
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["cards"][0]["key"], "sidekick:100111")

        saved = self.client.put(
            "/api/assistant/cards/sidekick:100111/tags",
            json={"tagIds": ["target-self", "value-damage"], "pinnedTagIds": ["value-damage"]},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["config"]["assignments"], {"sidekick:100111": ["target-self", "value-damage"]})
        self.assertEqual(saved.json()["config"]["pinnedAssignments"], {"sidekick:100111": ["value-damage"]})

        saved_without_pins = self.client.put(
            "/api/assistant/cards/sidekick:100111/tags",
            json={"tagIds": ["target-self"]},
        )
        self.assertEqual(saved_without_pins.status_code, 200)
        self.assertEqual(saved_without_pins.json()["config"]["pinnedAssignments"], {})

        rejected = self.client.put("/api/assistant/cards/sidekick:100111/tags", json={"tagIds": ["targeting"]})
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("叶子标签", rejected.json()["detail"])

    def test_creates_a_child_tag(self):
        created = self.client.post(
            "/api/assistant/tags",
            json={"id": "damage-over-time", "label": "持续伤害", "parentId": "effect"},
        )

        self.assertEqual(created.status_code, 200)
        self.assertIn(
            {"id": "damage-over-time", "label": "持续伤害", "parentId": "effect"},
            created.json()["config"]["tags"],
        )

    def test_reorders_complete_sibling_group_and_rejects_invalid_order(self):
        child_ids = ["target-none", "target-enemy-all", "target-enemy-multi", "target-enemy-single", "target-ally-all", "target-ally-multi", "target-ally-single", "target-self"]

        saved = self.client.put("/api/assistant/tags/order", json={"parentId": "targeting", "tagIds": child_ids})

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            [tag["id"] for tag in saved.json()["config"]["tags"] if tag["parentId"] == "targeting"],
            child_ids,
        )

        rejected = self.client.put("/api/assistant/tags/order", json={"parentId": "targeting", "tagIds": ["target-self"]})
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("全部直接子标签", rejected.json()["detail"])

    def test_delete_requires_confirmation_and_clears_affected_assignments(self):
        self.client.put(
            "/api/assistant/cards/sidekick:100111/tags",
            json={"tagIds": ["target-self"], "pinnedTagIds": ["target-self"]},
        )

        preview = self.client.delete("/api/assistant/tags/targeting")
        self.assertEqual(preview.status_code, 409)
        self.assertEqual(preview.json()["detail"]["affected"], 1)

        deleted = self.client.delete("/api/assistant/tags/targeting?confirm=true")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["config"]["assignments"], {})
        self.assertEqual(deleted.json()["config"]["pinnedAssignments"], {})


if __name__ == "__main__":
    unittest.main()
