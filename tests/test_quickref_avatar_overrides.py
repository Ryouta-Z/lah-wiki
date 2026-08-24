import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_targeted_quickref_avatars import SOLDIER_AVATAR_TARGETS
from scripts.lah_quickref import _avatar_for_card, _avatar_index, render_static_html


class QuickrefAvatarOverridesTest(unittest.TestCase):
    def test_soldier_targets_cover_all_resource_and_attribute_variants(self):
        self.assertEqual(len(SOLDIER_AVATAR_TARGETS), 42)
        for code, (pattern, texture_name) in SOLDIER_AVATAR_TARGETS.items():
            self.assertEqual(pattern, f"{code.lower()}_assets_all_*.bundle")
            self.assertEqual(texture_name, f"icon_{code}_h01")

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


if __name__ == "__main__":
    unittest.main()
