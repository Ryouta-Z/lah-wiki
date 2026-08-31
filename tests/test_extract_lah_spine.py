import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from scripts.extract_lah_spine import ExtractionError, extract


class FakeObject:
    def __init__(self, path_id, type_name, name="", tree=None, script=None, image=None):
        self.path_id = path_id
        self.type = SimpleNamespace(name=type_name)
        self._tree = tree or {}
        self._value = SimpleNamespace(m_Name=name, m_Script=script, image=image)

    def read(self):
        return self._value

    def read_typetree(self):
        return self._tree


def local_ref(path_id):
    return {"m_FileID": 0, "m_PathID": path_id}


def fake_environment(include_texture=True, second_skeleton=False):
    objects = [
        FakeObject(
            1,
            "MonoBehaviour",
            "spine_akashi_SkeletonData",
            {
                "m_Name": "spine_akashi_SkeletonData",
                "skeletonJSON": local_ref(2),
                "atlasAssets": [local_ref(3)],
            },
        ),
        FakeObject(
            2,
            "TextAsset",
            "spine_akashi",
            script=json.dumps(
                {
                    "skeleton": {"spine": "4.1.23"},
                    "animations": {"Idle": {}, "Attack": {}},
                }
            ),
        ),
        FakeObject(
            3,
            "MonoBehaviour",
            "spine_akashi_Atlas",
            {"m_Name": "spine_akashi_Atlas", "atlasFile": local_ref(4), "materials": [local_ref(5)]},
        ),
        FakeObject(4, "TextAsset", "spine_akashi.atlas", script="spine_akashi.png\nsize: 2,2\n"),
        FakeObject(
            5,
            "Material",
            "spine_akashi_Material",
            {
                "m_SavedProperties": {
                    "m_TexEnvs": [["_MainTex", {"m_Texture": local_ref(6)}]]
                }
            },
        ),
    ]
    if include_texture:
        objects.append(FakeObject(6, "Texture2D", "spine_akashi", image=Image.new("RGBA", (2, 2))))
    if second_skeleton:
        objects.append(
            FakeObject(
                7,
                "MonoBehaviour",
                "spine_akashiShadow_SkeletonData",
                {
                    "m_Name": "spine_akashiShadow_SkeletonData",
                    "skeletonJSON": local_ref(2),
                    "atlasAssets": [local_ref(3)],
                },
            )
        )
    return SimpleNamespace(objects=objects)


class ExtractLahSpineTest(unittest.TestCase):
    def test_extracts_a_reusable_spine_package_and_replaces_its_own_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "akashi.bundle"
            bundle.write_bytes(b"bundle-data")
            output = root / "akashi"

            with patch("scripts.extract_lah_spine.UnityPy.load", return_value=fake_environment()):
                first = extract(bundle, output)
                second = extract(bundle, output)

            self.assertEqual(first.animations, ("Attack", "Idle"))
            self.assertEqual(second.animations, ("Attack", "Idle"))
            self.assertEqual(
                sorted(path.name for path in output.iterdir()),
                ["manifest.json", "spine_akashi.atlas", "spine_akashi.json", "spine_akashi.png"],
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["spine_version"], "4.1.23")
            self.assertEqual(manifest["animations"], ["Attack", "Idle"])
            self.assertEqual(manifest["textures"][0]["file"], "spine_akashi.png")
            page = manifest["atlases"][0]["pages"][0]
            self.assertEqual(page["file"], "spine_akashi.png")
            self.assertEqual(page["material"]["source_name"], "spine_akashi_Material")
            self.assertEqual(page["texture"]["object_path_id"], 6)
            self.assertIn("spine_runtime_validation_unavailable", [entry["code"] for entry in manifest["diagnostics"]])

    def test_invalid_package_leaves_an_existing_successful_output_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "akashi.bundle"
            bundle.write_bytes(b"bundle-data")
            output = root / "akashi"
            output.mkdir()
            marker = output / "manifest.json"
            marker.write_text('{"previous": true}', encoding="utf-8")

            with patch(
                "scripts.extract_lah_spine.UnityPy.load", return_value=fake_environment(include_texture=False)
            ):
                with self.assertRaisesRegex(ExtractionError, "_MainTex"):
                    extract(bundle, output)

            self.assertEqual(marker.read_text(encoding="utf-8"), '{"previous": true}')

    def test_selects_a_named_skeleton_when_a_bundle_contains_multiple_skeletons(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "akashi.bundle"
            bundle.write_bytes(b"bundle-data")
            output = root / "akashi"

            with patch(
                "scripts.extract_lah_spine.UnityPy.load",
                return_value=fake_environment(second_skeleton=True),
            ):
                result = extract(bundle, output, skeleton_name="spine_akashi_SkeletonData")

            self.assertEqual(result.animations, ("Attack", "Idle"))
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["skeleton_data"]["name"], "spine_akashi_SkeletonData")


if __name__ == "__main__":
    unittest.main()
