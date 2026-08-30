"""Extract a reusable Spine package from a local Live A Hero Unity bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import UnityPy


ROOT = Path(__file__).parent.parent
DEFAULT_BUNDLE = ROOT / "data" / "cache" / "bundles" / "akashi.bundle"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "lah-spine" / "akashi"


class ExtractionError(RuntimeError):
    """The bundle does not expose a complete, local Spine package."""


@dataclass(frozen=True)
class ExtractionResult:
    output_dir: Path
    animations: tuple[str, ...]


def _safe_filename(name: str, label: str) -> str:
    filename = Path(name).name
    if not filename or filename != name or filename in {".", ".."}:
        raise ExtractionError(f"Unsafe {label} filename: {name!r}")
    return filename


def _script_text(obj: Any, label: str) -> str:
    value = getattr(obj.read(), "m_Script", None)
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ExtractionError(f"{label} does not contain text data")


def _path_id(reference: dict[str, Any], label: str) -> int:
    if reference.get("m_FileID") != 0 or not reference.get("m_PathID"):
        raise ExtractionError(f"{label} is not a local bundle reference")
    return reference["m_PathID"]


def _object(objects: dict[int, Any], reference: dict[str, Any], label: str) -> Any:
    path_id = _path_id(reference, label)
    try:
        return objects[path_id]
    except KeyError as error:
        raise ExtractionError(f"{label} points to missing object {path_id}") from error


def _tree(obj: Any, label: str) -> dict[str, Any]:
    try:
        return obj.read_typetree()
    except Exception as error:
        raise ExtractionError(f"Could not read {label} metadata") from error


def _spine_skeleton(objects: dict[int, Any]) -> tuple[Any, dict[str, Any]]:
    candidates = []
    for obj in objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        metadata = _tree(obj, "MonoBehaviour")
        if "skeletonJSON" in metadata and "atlasAssets" in metadata:
            candidates.append((obj, metadata))
    if len(candidates) != 1:
        raise ExtractionError(f"Expected one Spine SkeletonData asset, found {len(candidates)}")
    return candidates[0]


def _main_texture(
    material: Any, objects: dict[int, Any], diagnostics: list[dict[str, Any]], atlas_name: str, page: str
) -> Any:
    metadata = _tree(material, "Spine material")
    properties = metadata.get("m_SavedProperties", {})
    for item in properties.get("m_TexEnvs", []):
        if len(item) != 2:
            continue
        property_name, property_value = item
        reference = property_value.get("m_Texture", {})
        if property_name == "_MainTex":
            return _object(objects, reference, "Spine material _MainTex")
        if reference.get("m_FileID"):
            diagnostics.append(
                {
                    "code": "external_material_texture_reference",
                    "atlas": atlas_name,
                    "page": page,
                    "material": getattr(material.read(), "m_Name", ""),
                    "property": property_name,
                    "file_id": reference["m_FileID"],
                }
            )
    raise ExtractionError("Spine material does not contain a local _MainTex texture")


def _atlas_pages(atlas_text: str) -> list[str]:
    pages = []
    for block in atlas_text.replace("\r\n", "\n").split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines:
            pages.append(_safe_filename(lines[0], "atlas page"))
    if not pages:
        raise ExtractionError("Spine atlas does not name any texture pages")
    return pages


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_package(bundle_path: Path, staging_dir: Path) -> tuple[str, ...]:
    environment = UnityPy.load(str(bundle_path))
    objects = {obj.path_id: obj for obj in environment.objects}
    skeleton_asset, skeleton_metadata = _spine_skeleton(objects)
    skeleton_text_asset = _object(objects, skeleton_metadata["skeletonJSON"], "SkeletonData skeletonJSON")
    skeleton_name = _safe_filename(getattr(skeleton_text_asset.read(), "m_Name", ""), "skeleton")
    skeleton_file = f"{skeleton_name}.json"
    skeleton_text = _script_text(skeleton_text_asset, "Spine skeleton")
    try:
        skeleton = json.loads(skeleton_text)
    except json.JSONDecodeError as error:
        raise ExtractionError("Spine skeleton JSON is invalid") from error
    if not isinstance(skeleton, dict) or not isinstance(skeleton.get("animations"), dict):
        raise ExtractionError("Spine skeleton has no animations object")
    animations = tuple(sorted(skeleton["animations"]))
    if not animations:
        raise ExtractionError("Spine skeleton has no animations")

    diagnostics = []
    atlas_entries = []
    texture_entries = []
    written_textures: set[str] = set()
    for atlas_reference in skeleton_metadata["atlasAssets"]:
        atlas_asset = _object(objects, atlas_reference, "SkeletonData atlasAssets")
        atlas_metadata = _tree(atlas_asset, "Spine atlas")
        atlas_text_asset = _object(objects, atlas_metadata.get("atlasFile", {}), "Spine atlasFile")
        atlas_name = _safe_filename(getattr(atlas_text_asset.read(), "m_Name", ""), "atlas")
        atlas_text = _script_text(atlas_text_asset, "Spine atlas")
        pages = _atlas_pages(atlas_text)
        materials = [
            _object(objects, reference, "Spine atlas material")
            for reference in atlas_metadata.get("materials", [])
        ]
        if len(materials) != len(pages):
            raise ExtractionError(
                f"Spine atlas {atlas_name} has {len(pages)} pages but {len(materials)} materials"
            )
        (staging_dir / atlas_name).write_text(atlas_text, encoding="utf-8")
        page_entries = []
        for page, material in zip(pages, materials, strict=True):
            texture = _main_texture(material, objects, diagnostics, atlas_name, page)
            if texture.type.name != "Texture2D":
                raise ExtractionError(f"Spine material _MainTex for {page} is not a Texture2D")
            texture_name = _safe_filename(page, "texture")
            if texture_name not in written_textures:
                try:
                    texture.read().image.convert("RGBA").save(staging_dir / texture_name)
                except Exception as error:
                    raise ExtractionError(f"Could not save Spine texture {texture_name}") from error
                written_textures.add(texture_name)
            texture_entries.append(
                {
                    "file": texture_name,
                    "object_path_id": texture.path_id,
                    "source_name": getattr(texture.read(), "m_Name", ""),
                }
            )
            page_entries.append(
                {
                    "file": texture_name,
                    "material": {
                        "object_path_id": material.path_id,
                        "source_name": getattr(material.read(), "m_Name", ""),
                    },
                    "texture": {
                        "object_path_id": texture.path_id,
                        "source_name": getattr(texture.read(), "m_Name", ""),
                    },
                }
            )
        atlas_entries.append(
            {
                "file": atlas_name,
                "object_path_id": atlas_text_asset.path_id,
                "source_name": getattr(atlas_asset.read(), "m_Name", ""),
                "pages": page_entries,
            }
        )

    (staging_dir / skeleton_file).write_text(skeleton_text, encoding="utf-8")
    diagnostics.append(
        {
            "code": "spine_runtime_validation_unavailable",
            "message": "Structural validation completed; no compatible Spine runtime is bundled for rendering validation.",
            "spine_version": skeleton.get("skeleton", {}).get("spine"),
        }
    )
    manifest = {
        "input": {"file": bundle_path.name, "sha256": _sha256(bundle_path)},
        "skeleton": {"file": skeleton_file, "object_path_id": skeleton_text_asset.path_id},
        "skeleton_data": {"name": skeleton_metadata.get("m_Name", ""), "object_path_id": skeleton_asset.path_id},
        "spine_version": skeleton.get("skeleton", {}).get("spine"),
        "animations": list(animations),
        "atlases": atlas_entries,
        "textures": texture_entries,
        "diagnostics": diagnostics,
    }
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return animations


def _validate_package(output_dir: Path) -> tuple[str, ...]:
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    skeleton_path = output_dir / manifest["skeleton"]["file"]
    skeleton = json.loads(skeleton_path.read_text(encoding="utf-8"))
    animations = tuple(sorted(skeleton.get("animations", {})))
    if not animations or animations != tuple(manifest["animations"]):
        raise ExtractionError("Exported skeleton animations do not match the manifest")
    textures = {entry["file"] for entry in manifest["textures"]}
    for atlas in manifest["atlases"]:
        pages = _atlas_pages((output_dir / atlas["file"]).read_text(encoding="utf-8"))
        missing = [page for page in pages if page not in textures or not (output_dir / page).is_file()]
        if missing:
            raise ExtractionError(f"Spine atlas references missing texture pages: {', '.join(missing)}")
    return animations


def _replace_output(staging_dir: Path, output_dir: Path) -> None:
    if not output_dir.exists():
        staging_dir.replace(output_dir)
        return
    if not (output_dir / "manifest.json").is_file():
        raise ExtractionError(f"Refusing to replace unmanaged output directory: {output_dir}")
    backup_dir = output_dir.with_name(f".{output_dir.name}.previous")
    if backup_dir.exists():
        raise ExtractionError(f"Refusing to replace output while backup exists: {backup_dir}")
    output_dir.replace(backup_dir)
    try:
        staging_dir.replace(output_dir)
    except Exception:
        backup_dir.replace(output_dir)
        raise
    shutil.rmtree(backup_dir)


def extract(bundle_path: Path = DEFAULT_BUNDLE, output_dir: Path = DEFAULT_OUTPUT_DIR) -> ExtractionResult:
    """Export one bundle's directly referenced Spine package without partial output."""
    bundle_path = bundle_path.resolve()
    output_dir = output_dir.resolve()
    if not bundle_path.is_file():
        raise ExtractionError(f"Bundle not found: {bundle_path}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        animations = _write_package(bundle_path, staging_dir)
        validated_animations = _validate_package(staging_dir)
        if animations != validated_animations:
            raise ExtractionError("Export validation changed the animation list")
        _replace_output(staging_dir, output_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise
    return ExtractionResult(output_dir=output_dir, animations=animations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = extract(args.bundle, args.output_dir)
    print(f"Exported {len(result.animations)} Spine animations to {result.output_dir}")


if __name__ == "__main__":
    main()
