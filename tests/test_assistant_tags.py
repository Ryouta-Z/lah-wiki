import unittest

from scripts.assistant_tags import (
    default_assistant_tag_config,
    delete_tag,
    ordered_tag_ids,
    reorder_tag_siblings,
    tag_paths,
    tags_for_assignments,
    validate_assistant_tag_config,
)


class AssistantTagsTest(unittest.TestCase):
    def test_default_tree_has_expected_leaf_paths(self):
        config = default_assistant_tag_config()
        paths = tag_paths(config)

        self.assertEqual(paths["target-self"], ("作用目标", "自身"))
        self.assertEqual(paths["auto-skill-2"], ("自动战斗", "释放技能 2"))

    def test_assignments_must_reference_known_sidekick_leaf_tags(self):
        config = default_assistant_tag_config()
        config["assignments"] = {"sidekick:100": ["target-self", "target-none", "value-damage"]}

        validated = validate_assistant_tag_config(config, {"sidekick:100"})
        self.assertEqual(validated["assignments"]["sidekick:100"], ["target-self", "target-none", "value-damage"])

        config["assignments"] = {"sidekick:100": ["targeting"]}
        with self.assertRaisesRegex(ValueError, "叶子标签"):
            validate_assistant_tag_config(config, {"sidekick:100"})

        config["assignments"] = {"sidekick:missing": ["target-self"]}
        with self.assertRaisesRegex(ValueError, "助手"):
            validate_assistant_tag_config(config, {"sidekick:100"})

    def test_rejects_parent_cycles_and_removes_subtree_assignments(self):
        config = default_assistant_tag_config()
        config["tags"][0]["parentId"] = "target-self"
        with self.assertRaisesRegex(ValueError, "循环"):
            validate_assistant_tag_config(config)

        config = default_assistant_tag_config()
        config["assignments"] = {"sidekick:100": ["target-self", "target-none", "value-damage"]}
        removed = delete_tag(config, "targeting")

        self.assertEqual(removed, {"targeting", "target-self", "target-ally-single", "target-ally-multi", "target-ally-all", "target-enemy-single", "target-enemy-multi", "target-enemy-all", "target-none"})
        self.assertEqual(config["assignments"], {"sidekick:100": ["value-damage"]})

    def test_reorders_only_complete_sibling_groups(self):
        config = default_assistant_tag_config()
        config["assignments"] = {"sidekick:100": ["target-self", "target-none", "value-damage"]}
        reordered = [
            "target-none", "target-enemy-all", "target-enemy-multi", "target-enemy-single",
            "target-ally-all", "target-ally-multi", "target-ally-single", "target-self",
        ]

        reorder_tag_siblings(config, "targeting", reordered)

        self.assertEqual([tag["id"] for tag in config["tags"] if tag["parentId"] == "targeting"], reordered)
        self.assertEqual(config["assignments"], {"sidekick:100": ["target-self", "target-none", "value-damage"]})
        self.assertLess(ordered_tag_ids(config).index("target-none"), ordered_tag_ids(config).index("target-self"))
        self.assertEqual(
            [tag["id"] for tag in tags_for_assignments(config)["sidekick:100"]],
            ["target-none", "target-self", "value-damage"],
        )

        with self.assertRaisesRegex(ValueError, "全部直接子标签"):
            reorder_tag_siblings(config, "targeting", ["target-self"])
        with self.assertRaisesRegex(ValueError, "重复"):
            reorder_tag_siblings(config, "targeting", ["target-self"] * len(reordered))
        with self.assertRaisesRegex(ValueError, "全部直接子标签"):
            reorder_tag_siblings(config, "targeting", [*reordered[:-1], "value-damage"])


if __name__ == "__main__":
    unittest.main()
