"""Extract the approved quick-reference avatars from copied Unity bundles."""

from __future__ import annotations

import argparse
from pathlib import Path

import UnityPy
from PIL import Image


ROOT = Path(__file__).parent.parent
DEFAULT_SOURCE_DIR = ROOT / "data" / "cache" / "targeted-avatars" / "20260824"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "images" / "icon"
AVATAR_TARGETS = {
    "garbo": ("garbo_assets_all_*.bundle", "icon_garbo_h01"),
    "roikermontage2607": (
        "roikermontage2607_assets_all_*.bundle",
        "icon_roikerMontage2607_h01",
    ),
    "shiratori": ("shiratori_assets_all_*.bundle", "icon_shiratori_h01"),
    "ruchbath": ("ruchbath_assets_all_*.bundle", "icon_ruchbath_h01"),
    "tsuneakirookies2408": (
        "tsuneakirookies2408_assets_all_*.bundle",
        "icon_tsuneakiRookies2408_h01",
    ),
    "yvaga": ("yvaga_assets_all_*.bundle", "icon_yvaga_h01"),
}
SOLDIER_RESOURCE_BASES = (
    "androidSoldier",
    "apprentice",
    "diver",
    "guardman",
    "localIdol",
    "mercenary",
    "trainee",
    "wrestler",
)
SOLDIER_RESOURCE_CODES = (
    tuple(
        f"{base}{element}"
        for base in SOLDIER_RESOURCE_BASES
        for element in ("Fire", "Water", "Earth", "Light", "Shadow")
    )
    + ("wolfmanEarth", "wolfmanShadow")
)
SOLDIER_AVATAR_TARGETS = {
    code: (f"{code.lower()}_assets_all_*.bundle", f"icon_{code}_h01")
    for code in SOLDIER_RESOURCE_CODES
}
PLAYER_TARGETS = [
    (f"player{number}_assets_all_*.bundle", f"icon_player{number}_s01")
    for number in range(1, 5)
]


def _bundle(source_dir: Path, pattern: str) -> Path:
    matches = list(source_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one bundle for {pattern}, found {len(matches)}")
    return matches[0]


def _texture(bundle_path: Path, texture_name: str) -> Image.Image:
    for obj in UnityPy.load(str(bundle_path)).objects:
        if obj.type.name != "Texture2D":
            continue
        texture = obj.read()
        if texture.m_Name == texture_name:
            return texture.image.convert("RGBA")
    raise RuntimeError(f"Texture {texture_name} not found in {bundle_path.name}")


def extract(source_dir: Path = DEFAULT_SOURCE_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for code, (pattern, texture_name) in {
        **AVATAR_TARGETS,
        **SOLDIER_AVATAR_TARGETS,
    }.items():
        output_path = output_dir / f"{code.lower()}.png"
        _texture(_bundle(source_dir, pattern), texture_name).save(output_path)
        written.append(output_path)

    player_frames = [
        _texture(_bundle(source_dir, pattern), texture_name)
        for pattern, texture_name in PLAYER_TARGETS
    ]
    player_path = output_dir / "player.gif"
    player_frames[0].save(
        player_path,
        save_all=True,
        append_images=player_frames[1:],
        duration=900,
        loop=0,
        disposal=2,
    )
    written.append(player_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    for path in extract(args.source_dir, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
