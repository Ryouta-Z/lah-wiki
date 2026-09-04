"""Independent public Live A Hero hero-tag configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.card_tags import (
        delete_tag as _delete_tag, default_tag_config, ordered_tag_ids as _ordered_tag_ids,
        read_tag_config, reorder_tag_siblings as _reorder_tag_siblings,
        tag_paths as _tag_paths, tags_for_assignments as _tags_for_assignments,
        validate_tag_config, write_tag_config,
    )
except ModuleNotFoundError:  # Allow `python scripts/lah_quickref.py` from the project root.
    from card_tags import (  # type: ignore[no-redef]
        delete_tag as _delete_tag, default_tag_config, ordered_tag_ids as _ordered_tag_ids,
        read_tag_config, reorder_tag_siblings as _reorder_tag_siblings,
        tag_paths as _tag_paths, tags_for_assignments as _tags_for_assignments,
        validate_tag_config, write_tag_config,
    )

ROOT = Path(__file__).parent.parent
DEFAULT_HERO_TAGS_PATH = ROOT / "data" / "hero_tags.json"
_OPTIONS = {"key_prefix": "hero", "entity_label": "英雄"}

def default_hero_tag_config() -> dict[str, Any]: return default_tag_config()
def read_hero_tag_config(path: Path = DEFAULT_HERO_TAGS_PATH) -> dict[str, Any]: return read_tag_config(path, **_OPTIONS)
def write_hero_tag_config(path: Path, config: dict[str, Any]) -> None: write_tag_config(path, config, **_OPTIONS)
def validate_hero_tag_config(config: dict[str, Any], valid_hero_keys: Iterable[str] | None = None) -> dict[str, Any]: return validate_tag_config(config, valid_card_keys=valid_hero_keys, **_OPTIONS)
def tag_paths(config: dict[str, Any]) -> dict[str, tuple[str, ...]]: return _tag_paths(config, **_OPTIONS)
def ordered_tag_ids(config: dict[str, Any]) -> list[str]: return _ordered_tag_ids(config, **_OPTIONS)
def reorder_tag_siblings(config: dict[str, Any], parent_id: str | None, tag_ids: list[str]) -> None: _reorder_tag_siblings(config, parent_id, tag_ids, **_OPTIONS)
def tags_for_assignments(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]: return _tags_for_assignments(config, **_OPTIONS)
def delete_tag(config: dict[str, Any], tag_id: str) -> set[str]: return _delete_tag(config, tag_id, **_OPTIONS)
