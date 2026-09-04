"""Independent public Live A Hero assistant-tag configuration."""

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
DEFAULT_ASSISTANT_TAGS_PATH = ROOT / "data" / "assistant_tags.json"
MAX_PINNED_TAGS_PER_ASSISTANT = 3
_OPTIONS = {"key_prefix": "sidekick", "entity_label": "助手"}
_DEFAULT_TAGS = [
    {"id": "targeting", "label": "作用目标", "parentId": None},
    {"id": "target-self", "label": "自身", "parentId": "targeting"},
    {"id": "target-ally-single", "label": "友方单体", "parentId": "targeting"},
    {"id": "target-ally-multi", "label": "友方多目标", "parentId": "targeting"},
    {"id": "target-ally-all", "label": "友方全体", "parentId": "targeting"},
    {"id": "target-enemy-single", "label": "敌方单体", "parentId": "targeting"},
    {"id": "target-enemy-multi", "label": "敌方多目标", "parentId": "targeting"},
    {"id": "target-enemy-all", "label": "敌方全体", "parentId": "targeting"},
    {"id": "target-none", "label": "无目标", "parentId": "targeting"},
    {"id": "value", "label": "作用数值", "parentId": None},
    {"id": "value-damage", "label": "伤害", "parentId": "value"},
    {"id": "value-recovery", "label": "恢复", "parentId": "value"},
    {"id": "value-shield", "label": "护盾", "parentId": "value"},
    {"id": "value-view", "label": "View 相关", "parentId": "value"},
    {"id": "buff", "label": "Buff 类型", "parentId": None},
    {"id": "buff-dispellable", "label": "可驱散", "parentId": "buff"},
    {"id": "buff-undispellable", "label": "不可驱散", "parentId": "buff"},
    {"id": "effect", "label": "作用效果", "parentId": None},
    {"id": "effect-damage-up", "label": "增伤", "parentId": "effect"},
    {"id": "effect-damage-down", "label": "减伤", "parentId": "effect"},
    {"id": "auto-battle", "label": "自动战斗", "parentId": None},
    {"id": "auto-target-selection", "label": "自动选择目标", "parentId": "auto-battle"},
    {"id": "auto-skill-2", "label": "释放技能 2", "parentId": "auto-battle"},
    {"id": "auto-skill-3", "label": "释放技能 3", "parentId": "auto-battle"},
    {"id": "auto-mixed-skill", "label": "混合释放", "parentId": "auto-battle"},
]

def default_assistant_tag_config() -> dict[str, Any]: return default_tag_config(_DEFAULT_TAGS)
def read_assistant_tag_config(path: Path = DEFAULT_ASSISTANT_TAGS_PATH) -> dict[str, Any]: return read_tag_config(path, default_tags=_DEFAULT_TAGS, **_OPTIONS)
def write_assistant_tag_config(path: Path, config: dict[str, Any]) -> None: write_tag_config(path, config, **_OPTIONS)
def validate_assistant_tag_config(config: dict[str, Any], valid_sidekick_keys: Iterable[str] | None = None) -> dict[str, Any]: return validate_tag_config(config, valid_card_keys=valid_sidekick_keys, **_OPTIONS)
def tag_paths(config: dict[str, Any]) -> dict[str, tuple[str, ...]]: return _tag_paths(config, **_OPTIONS)
def ordered_tag_ids(config: dict[str, Any]) -> list[str]: return _ordered_tag_ids(config, **_OPTIONS)
def reorder_tag_siblings(config: dict[str, Any], parent_id: str | None, tag_ids: list[str]) -> None: _reorder_tag_siblings(config, parent_id, tag_ids, **_OPTIONS)
def tags_for_assignments(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]: return _tags_for_assignments(config, **_OPTIONS)
def delete_tag(config: dict[str, Any], tag_id: str) -> set[str]: return _delete_tag(config, tag_id, **_OPTIONS)
