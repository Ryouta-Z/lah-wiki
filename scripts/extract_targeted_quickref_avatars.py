"""Extract the approved quick-reference avatars from copied Unity bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import UnityPy
from PIL import Image


ROOT = Path(__file__).parent.parent
DEFAULT_SOURCE_DIR = ROOT / "data" / "cache" / "targeted-avatars" / "20260824"
DEFAULT_SIDEKICK_SOURCE_DIR = ROOT / "data" / "cache" / "lah-spine-bundles"
DEFAULT_SIDEKICK_SNAPSHOT_DIR = ROOT / "data" / "cache" / "lah-localization"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "images" / "icon"
DEFAULT_SIDEKICK_OVERRIDES_PATH = ROOT / "data" / "quickref_sidekick_avatar_overrides.json"
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


def sidekick_avatar_targets(
    snapshot_dir: Path = DEFAULT_SIDEKICK_SNAPSHOT_DIR,
) -> dict[str, tuple[str, str]]:
    snapshots = sorted(snapshot_dir.glob("SidekickMaster-*"), key=lambda path: path.stat().st_mtime)
    if not snapshots:
        raise RuntimeError(f"No SidekickMaster snapshot found in {snapshot_dir}")
    raw_cards = json.loads(snapshots[-1].read_text(encoding="utf-8"))
    entries = raw_cards.values() if isinstance(raw_cards, dict) else raw_cards
    resources = {
        resource.lower(): resource
        for card in entries
        if isinstance(card, dict)
        if isinstance(resource := card.get("resourceName"), str)
        if resource and resource.lower() != "player"
    }
    return {
        f"{code}-sidekick": (f"{code}_assets_all_*.bundle", f"icon_{resource}_s01")
        for code, resource in sorted(resources.items())
    }


def _bundle(source_dirs: Path | Iterable[Path], pattern: str) -> Path:
    directories = (source_dirs,) if isinstance(source_dirs, Path) else tuple(source_dirs)
    matches = [match for source_dir in directories for match in source_dir.glob(pattern)]
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


def _extract_targets(
    source_dirs: Path | Iterable[Path],
    output_dir: Path,
    targets: dict[str, tuple[str, str]],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for code, (pattern, texture_name) in targets.items():
        output_path = output_dir / f"{code.lower()}.png"
        _texture(_bundle(source_dirs, pattern), texture_name).save(output_path)
        written.append(output_path)
    return written


def extract(source_dir: Path = DEFAULT_SOURCE_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    written = _extract_targets(
        source_dir, output_dir, {**AVATAR_TARGETS, **SOLDIER_AVATAR_TARGETS}
    )

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


def extract_sidekick_cases(
    source_dir: Path = DEFAULT_SIDEKICK_SOURCE_DIR,
    snapshot_dir: Path = DEFAULT_SIDEKICK_SNAPSHOT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    return _extract_targets(
        (source_dir, DEFAULT_SOURCE_DIR),
        output_dir,
        sidekick_avatar_targets(snapshot_dir),
    )


def write_sidekick_avatar_overrides(
    overrides_path: Path,
    targets: dict[str, tuple[str, str]],
) -> None:
    overrides = {
        target.removesuffix("-sidekick"): f"{target}.png"
        for target in targets
    }
    overrides["player"] = "player.gif"
    overrides_path.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sidekick-source-dir", type=Path, default=DEFAULT_SIDEKICK_SOURCE_DIR)
    parser.add_argument("--sidekick-snapshot-dir", type=Path, default=DEFAULT_SIDEKICK_SNAPSHOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sidekick-overrides-path", type=Path, default=DEFAULT_SIDEKICK_OVERRIDES_PATH)
    parser.add_argument("--sidekick-cases", action="store_true")
    args = parser.parse_args()
    if args.sidekick_cases:
        targets = sidekick_avatar_targets(args.sidekick_snapshot_dir)
        extracted = _extract_targets(
            (args.sidekick_source_dir, args.source_dir), args.output_dir, targets
        )
        write_sidekick_avatar_overrides(args.sidekick_overrides_path, targets)
    else:
        extracted = extract(args.source_dir, args.output_dir)
    for path in extracted:
        print(path)


if __name__ == "__main__":
    main()
