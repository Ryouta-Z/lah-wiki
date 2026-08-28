"""Shared public assistant-tag configuration and validation."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable


ROOT = Path(__file__).parent.parent
DEFAULT_ASSISTANT_TAGS_PATH = ROOT / "data" / "assistant_tags.json"

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


def default_assistant_tag_config() -> dict[str, Any]:
    return {"version": 1, "tags": deepcopy(_DEFAULT_TAGS), "assignments": {}}


def read_assistant_tag_config(path: Path = DEFAULT_ASSISTANT_TAGS_PATH) -> dict[str, Any]:
    if not path.exists():
        return default_assistant_tag_config()
    with path.open(encoding="utf-8") as file:
        return validate_assistant_tag_config(json.load(file))


def write_assistant_tag_config(path: Path, config: dict[str, Any]) -> None:
    validated = validate_assistant_tag_config(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as file:
        json.dump(validated, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary_path = Path(file.name)
    temporary_path.replace(path)


def validate_assistant_tag_config(
    config: dict[str, Any], valid_sidekick_keys: Iterable[str] | None = None
) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("助手标签配置必须是对象")
    if config.get("version") != 1:
        raise ValueError("助手标签配置版本必须为 1")
    tags = config.get("tags")
    assignments = config.get("assignments")
    if not isinstance(tags, list) or not isinstance(assignments, dict):
        raise ValueError("助手标签配置必须包含 tags 数组和 assignments 对象")

    normalized_tags = []
    tags_by_id = {}
    for tag in tags:
        if not isinstance(tag, dict):
            raise ValueError("标签必须是对象")
        tag_id = tag.get("id")
        label = tag.get("label")
        parent_id = tag.get("parentId")
        if not isinstance(tag_id, str) or not tag_id.strip():
            raise ValueError("标签 ID 不能为空")
        if tag_id in tags_by_id:
            raise ValueError(f"标签 ID 重复：{tag_id}")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"标签名称不能为空：{tag_id}")
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError(f"标签父级无效：{tag_id}")
        normalized = {"id": tag_id, "label": label.strip(), "parentId": parent_id}
        normalized_tags.append(normalized)
        tags_by_id[tag_id] = normalized

    for tag in normalized_tags:
        parent_id = tag["parentId"]
        if parent_id is not None and parent_id not in tags_by_id:
            raise ValueError(f"标签父级不存在：{tag['id']}")
        if parent_id == tag["id"]:
            raise ValueError(f"标签层级存在循环：{tag['id']}")

    for tag_id in tags_by_id:
        seen = set()
        current = tag_id
        while current is not None:
            if current in seen:
                raise ValueError(f"标签层级存在循环：{tag_id}")
            seen.add(current)
            current = tags_by_id[current]["parentId"]

    parent_ids = {tag["parentId"] for tag in normalized_tags if tag["parentId"] is not None}
    valid_keys = set(valid_sidekick_keys) if valid_sidekick_keys is not None else None
    normalized_assignments: dict[str, list[str]] = {}
    for sidekick_key, tag_ids in assignments.items():
        if not isinstance(sidekick_key, str) or not sidekick_key.startswith("sidekick:"):
            raise ValueError(f"标签归属必须使用助手键：{sidekick_key}")
        if valid_keys is not None and sidekick_key not in valid_keys:
            raise ValueError(f"标签归属引用了不存在的助手：{sidekick_key}")
        if not isinstance(tag_ids, list) or not all(isinstance(tag_id, str) for tag_id in tag_ids):
            raise ValueError(f"助手标签必须是字符串数组：{sidekick_key}")
        if len(tag_ids) != len(set(tag_ids)):
            raise ValueError(f"助手标签重复：{sidekick_key}")
        for tag_id in tag_ids:
            if tag_id not in tags_by_id:
                raise ValueError(f"助手标签不存在：{tag_id}")
            if tag_id in parent_ids:
                raise ValueError(f"助手只能分配叶子标签：{tag_id}")
        if tag_ids:
            normalized_assignments[sidekick_key] = list(tag_ids)

    return {"version": 1, "tags": normalized_tags, "assignments": normalized_assignments}


def tag_paths(config: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    validated = validate_assistant_tag_config(config)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    paths: dict[str, tuple[str, ...]] = {}

    def path_for(tag_id: str) -> tuple[str, ...]:
        if tag_id not in paths:
            tag = tags_by_id[tag_id]
            parent_id = tag["parentId"]
            paths[tag_id] = (*path_for(parent_id), tag["label"]) if parent_id else (tag["label"],)
        return paths[tag_id]

    for tag_id in tags_by_id:
        path_for(tag_id)
    return paths


def ordered_tag_ids(config: dict[str, Any]) -> list[str]:
    validated = validate_assistant_tag_config(config)
    children: dict[str | None, list[str]] = {}
    for tag in validated["tags"]:
        children.setdefault(tag["parentId"], []).append(tag["id"])

    ordered: list[str] = []

    def append_branch(parent_id: str | None) -> None:
        for tag_id in children.get(parent_id, []):
            ordered.append(tag_id)
            append_branch(tag_id)

    append_branch(None)
    return ordered


def reorder_tag_siblings(config: dict[str, Any], parent_id: str | None, tag_ids: list[str]) -> None:
    validated = validate_assistant_tag_config(config)
    if parent_id is not None and not any(tag["id"] == parent_id for tag in validated["tags"]):
        raise ValueError(f"标签父级不存在：{parent_id}")
    if not isinstance(tag_ids, list) or not all(isinstance(tag_id, str) for tag_id in tag_ids):
        raise ValueError("标签排序必须是标签 ID 数组")

    siblings = [tag for tag in validated["tags"] if tag["parentId"] == parent_id]
    sibling_ids = [tag["id"] for tag in siblings]
    if len(tag_ids) != len(set(tag_ids)):
        raise ValueError("标签排序不能包含重复标签")
    if set(tag_ids) != set(sibling_ids):
        raise ValueError("标签排序必须包含该分类下全部直接子标签")

    ordered_siblings = iter({tag["id"]: tag for tag in siblings}[tag_id] for tag_id in tag_ids)
    validated["tags"] = [
        next(ordered_siblings) if tag["parentId"] == parent_id else tag
        for tag in validated["tags"]
    ]
    config.clear()
    config.update(validate_assistant_tag_config(validated))


def tags_for_assignments(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    validated = validate_assistant_tag_config(config)
    paths = tag_paths(validated)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    order = {tag_id: index for index, tag_id in enumerate(ordered_tag_ids(validated))}
    return {
        sidekick_key: [
            {"id": tag_id, "label": tags_by_id[tag_id]["label"], "path": list(paths[tag_id])}
            for tag_id in sorted(tag_ids, key=lambda current_id: order[current_id])
        ]
        for sidekick_key, tag_ids in validated["assignments"].items()
    }


def delete_tag(config: dict[str, Any], tag_id: str) -> set[str]:
    validated = validate_assistant_tag_config(config)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    if tag_id not in tags_by_id:
        raise ValueError(f"标签不存在：{tag_id}")
    children: dict[str | None, list[str]] = {}
    for tag in validated["tags"]:
        children.setdefault(tag["parentId"], []).append(tag["id"])
    removed = set()
    pending = [tag_id]
    while pending:
        current = pending.pop()
        removed.add(current)
        pending.extend(children.get(current, []))
    validated["tags"] = [tag for tag in validated["tags"] if tag["id"] not in removed]
    validated["assignments"] = {
        sidekick_key: [assigned_id for assigned_id in tag_ids if assigned_id not in removed]
        for sidekick_key, tag_ids in validated["assignments"].items()
    }
    validated["assignments"] = {
        sidekick_key: tag_ids
        for sidekick_key, tag_ids in validated["assignments"].items()
        if tag_ids
    }
    config.clear()
    config.update(validate_assistant_tag_config(validated))
    return removed
