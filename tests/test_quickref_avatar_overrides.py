import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_targeted_quickref_avatars import (
    DEFAULT_SIDEKICK_SNAPSHOT_DIR,
    SOLDIER_AVATAR_TARGETS,
    sidekick_avatar_targets,
)
from scripts.lah_quickref import (
    DEFAULT_SNAPSHOT_DIR,
    _avatar_for_card,
    _avatar_index,
    _sidekick_avatar_overrides,
    build_catalog,
    render_static_html,
)


class QuickrefAvatarOverridesTest(unittest.TestCase):
    def test_soldier_targets_cover_all_resource_and_attribute_variants(self):
        self.assertEqual(len(SOLDIER_AVATAR_TARGETS), 42)
        for code, (pattern, texture_name) in SOLDIER_AVATAR_TARGETS.items():
            self.assertEqual(pattern, f"{code.lower()}_assets_all_*.bundle")
            self.assertEqual(texture_name, f"icon_{code}_h01")

    def test_sidekick_targets_cover_every_non_player_sidekick_portrait(self):
        targets = sidekick_avatar_targets(DEFAULT_SIDEKICK_SNAPSHOT_DIR)

        self.assertEqual(len(targets), 152)
        self.assertEqual(
            targets["akashi-sidekick"],
            ("akashi_assets_all_*.bundle", "icon_akashi_s01"),
        )
        self.assertEqual(
            targets["mokdai-sidekick"],
            ("mokdai_assets_all_*.bundle", "icon_mokdai_s01"),
        )
        self.assertEqual(
            targets["yvaga-sidekick"],
            ("yvaga_assets_all_*.bundle", "icon_yvaga_s01"),
        )
        self.assertEqual(
            targets["norbrand-sidekick"],
            ("norbrand_assets_all_*.bundle", "icon_norbrand_s01"),
        )
        self.assertNotIn("player-sidekick", targets)

    def test_resource_override_can_use_a_gif_without_changing_existing_png_avatars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icon_dir = root / "icons"
            icon_dir.mkdir()
            (icon_dir / "akashi.png").write_bytes(b"png")
            (icon_dir / "player.gif").write_bytes(b"gif")
            overrides_path = root / "avatar_overrides.json"
            overrides_path.write_text(
                json.dumps({"player": "player.gif"}), encoding="utf-8"
            )

            avatars = _avatar_index(
                {"akashi": {"cn": "赤司", "jp": "アカシ"}},
                icon_dir,
                overrides_path,
            )

        self.assertEqual(
            _avatar_for_card("player", "主人公", "主人公", avatars),
            {"status": "available", "code": "player", "filename": "player.gif"},
        )
        self.assertEqual(
            _avatar_for_card("akashi", "アカシ", "赤司", avatars),
            {"status": "available", "code": "akashi"},
        )
        self.assertIn(
            "avatar.filename || `${avatar.code}.png`",
            render_static_html({"cards": [], "statusTerms": []}),
        )

    def test_sidekick_overrides_use_a_dedicated_portrait_without_changing_hero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icon_dir = root / "icons"
            icon_dir.mkdir()
            (icon_dir / "akashi.png").write_bytes(b"hero")
            (icon_dir / "akashi-sidekick.png").write_bytes(b"sidekick")
            overrides_path = root / "sidekick_avatar_overrides.json"
            overrides_path.write_text(
                json.dumps({"akashi": "akashi-sidekick.png"}), encoding="utf-8"
            )

            avatars = _avatar_index(
                {"akashi": {"cn": "赤司", "jp": "アカシ"}}, icon_dir
            )
            sidekick_avatars = _sidekick_avatar_overrides(icon_dir, overrides_path)

        self.assertEqual(
            _avatar_for_card("akashi", "アカシ", "赤司", avatars),
            {"status": "available", "code": "akashi"},
        )
        self.assertEqual(
            _avatar_for_card(
                "akashi", "アカシ", "赤司", avatars, sidekick_avatars
            ),
            {
                "status": "available",
                "code": "akashi",
                "filename": "akashi-sidekick.png",
            },
        )

    def test_missing_sidekick_override_keeps_the_existing_avatar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icon_dir = root / "icons"
            icon_dir.mkdir()
            (icon_dir / "akashi.png").write_bytes(b"hero")
            overrides_path = root / "sidekick_avatar_overrides.json"
            overrides_path.write_text(
                json.dumps({"akashi": "akashi-sidekick.png"}), encoding="utf-8"
            )

            avatars = _avatar_index(
                {"akashi": {"cn": "赤司", "jp": "アカシ"}}, icon_dir
            )
            sidekick_avatars = _sidekick_avatar_overrides(icon_dir, overrides_path)

        self.assertEqual(
            _avatar_for_card(
                "akashi", "アカシ", "赤司", avatars, sidekick_avatars
            ),
            {"status": "available", "code": "akashi"},
        )

    def test_selected_sidekicks_use_dedicated_portraits_in_the_catalog(self):
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)
        cards_by_id = {card["cardId"]: card for card in catalog["cards"]}

        self.assertEqual(
            cards_by_id["100116"]["avatar"]["filename"], "akashi-sidekick.png"
        )
        self.assertEqual(
            cards_by_id["100216"]["avatar"]["filename"], "mokdai-sidekick.png"
        )
        self.assertEqual(
            cards_by_id["132716"]["avatar"]["filename"], "yvaga-sidekick.png"
        )
        self.assertNotEqual(
            cards_by_id["100114"]["avatar"].get("filename"),
            "akashi-sidekick.png",
        )
        self.assertNotEqual(
            cards_by_id["100214"]["avatar"].get("filename"),
            "mokdai-sidekick.png",
        )
        self.assertNotEqual(
            cards_by_id["132713"]["avatar"].get("filename"),
            "yvaga-sidekick.png",
        )

    def test_all_non_player_sidekicks_use_dedicated_portraits(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = build_catalog(
                DEFAULT_SNAPSHOT_DIR,
                sidekick_avatar_overrides_path=Path(directory) / "missing.json",
            )
        catalog = build_catalog(DEFAULT_SNAPSHOT_DIR)
        baseline_by_id = {card["cardId"]: card for card in baseline["cards"]}
        changed = [
            card
            for card in catalog["cards"]
            if card["kind"] == "sidekick"
            and card["avatar"] != baseline_by_id[card["cardId"]]["avatar"]
        ]

        self.assertEqual(len(changed), 152)
        self.assertTrue(
            all(card["avatar"]["filename"].endswith("-sidekick.png") for card in changed)
        )
        cards_by_id = {card["cardId"]: card for card in catalog["cards"]}
        self.assertEqual(cards_by_id["199916"]["avatar"]["filename"], "player.gif")
        self.assertEqual(
            cards_by_id["199916"]["avatar"], baseline_by_id["199916"]["avatar"]
        )


if __name__ == "__main__":
    unittest.main()
