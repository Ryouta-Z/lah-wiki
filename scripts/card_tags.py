"""Shared tree-tag validation for independently managed card groups."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable


MAX_PINNED_TAGS_PER_CARD = 3


def default_tag_config(default_tags: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    return {"version": 1, "tags": deepcopy(list(default_tags)), "assignments": {}, "pinnedAssignments": {}}


def read_tag_config(
    path: Path,
    *,
    key_prefix: str,
    entity_label: str,
    default_tags: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    if not path.exists():
        return default_tag_config(default_tags)
    with path.open(encoding="utf-8") as file:
        return validate_tag_config(json.load(file), key_prefix=key_prefix, entity_label=entity_label)


def write_tag_config(
    path: Path, config: dict[str, Any], *, key_prefix: str, entity_label: str
) -> None:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as file:
        json.dump(validated, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary_path = Path(file.name)
    temporary_path.replace(path)


def validate_tag_config(
    config: dict[str, Any],
    *,
    key_prefix: str,
    entity_label: str,
    valid_card_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError(f"{entity_label}标签配置版本必须为 1")
    tags = config.get("tags")
    assignments = config.get("assignments")
    pinned_assignments = config.get("pinnedAssignments", {})
    if not isinstance(tags, list) or not isinstance(assignments, dict) or not isinstance(pinned_assignments, dict):
        raise ValueError(f"{entity_label}标签配置必须包含 tags 数组和 assignments 对象")

    normalized_tags: list[dict[str, Any]] = []
    tags_by_id: dict[str, dict[str, Any]] = {}
    for tag in tags:
        if not isinstance(tag, dict):
            raise ValueError("标签必须是对象")
        tag_id, label, parent_id = tag.get("id"), tag.get("label"), tag.get("parentId")
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
        seen: set[str] = set()
        current = tag["id"]
        while current is not None:
            if current in seen:
                raise ValueError(f"标签层级存在循环：{tag['id']}")
            seen.add(current)
            current = tags_by_id[current]["parentId"]

    parent_ids = {tag["parentId"] for tag in normalized_tags if tag["parentId"] is not None}
    valid_keys = set(valid_card_keys) if valid_card_keys is not None else None

    def normalize_assignments(source: dict[str, Any], pinned: bool = False) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for card_key, tag_ids in source.items():
            if not isinstance(card_key, str) or not card_key.startswith(f"{key_prefix}:"):
                raise ValueError(f"标签归属必须使用{entity_label}键：{card_key}")
            if valid_keys is not None and card_key not in valid_keys:
                raise ValueError(f"标签归属引用了不存在的{entity_label}：{card_key}")
            if not isinstance(tag_ids, list) or not all(isinstance(tag_id, str) for tag_id in tag_ids):
                raise ValueError(f"{entity_label}标签必须是字符串数组：{card_key}")
            if len(tag_ids) != len(set(tag_ids)):
                raise ValueError(f"{entity_label}标签重复：{card_key}")
            if pinned and len(tag_ids) > MAX_PINNED_TAGS_PER_CARD:
                raise ValueError(f"每名{entity_label}最多置顶 {MAX_PINNED_TAGS_PER_CARD} 个标签：{card_key}")
            for tag_id in tag_ids:
                if tag_id not in tags_by_id:
                    raise ValueError(f"{entity_label}标签不存在：{tag_id}")
                if not pinned and tag_id in parent_ids:
                    raise ValueError(f"{entity_label}只能分配叶子标签：{tag_id}")
            if tag_ids:
                result[card_key] = list(tag_ids)
        return result

    normalized_assignments = normalize_assignments(assignments)
    normalized_pinned = normalize_assignments(pinned_assignments, pinned=True)
    for card_key, tag_ids in normalized_pinned.items():
        if not set(tag_ids).issubset(normalized_assignments.get(card_key, [])):
            raise ValueError(f"置顶标签必须已分配给{entity_label}：{card_key}")
    return {"version": 1, "tags": normalized_tags, "assignments": normalized_assignments, "pinnedAssignments": normalized_pinned}


def tag_paths(config: dict[str, Any], *, key_prefix: str, entity_label: str) -> dict[str, tuple[str, ...]]:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    paths: dict[str, tuple[str, ...]] = {}
    def path_for(tag_id: str) -> tuple[str, ...]:
        if tag_id not in paths:
            tag = tags_by_id[tag_id]
            paths[tag_id] = (*path_for(tag["parentId"]), tag["label"]) if tag["parentId"] else (tag["label"],)
        return paths[tag_id]
    for tag_id in tags_by_id:
        path_for(tag_id)
    return paths


def ordered_tag_ids(config: dict[str, Any], *, key_prefix: str, entity_label: str) -> list[str]:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
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


def reorder_tag_siblings(config: dict[str, Any], parent_id: str | None, tag_ids: list[str], *, key_prefix: str, entity_label: str) -> None:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
    if parent_id is not None and not any(tag["id"] == parent_id for tag in validated["tags"]):
        raise ValueError(f"标签父级不存在：{parent_id}")
    siblings = [tag for tag in validated["tags"] if tag["parentId"] == parent_id]
    sibling_ids = [tag["id"] for tag in siblings]
    if not isinstance(tag_ids, list) or not all(isinstance(tag_id, str) for tag_id in tag_ids) or len(tag_ids) != len(set(tag_ids)):
        raise ValueError("标签排序不能包含重复或无效标签")
    if set(tag_ids) != set(sibling_ids):
        raise ValueError("标签排序必须包含该分类下全部直接子标签")
    by_id = {tag["id"]: tag for tag in siblings}
    ordered_siblings = iter(by_id[tag_id] for tag_id in tag_ids)
    validated["tags"] = [next(ordered_siblings) if tag["parentId"] == parent_id else tag for tag in validated["tags"]]
    config.clear()
    config.update(validate_tag_config(validated, key_prefix=key_prefix, entity_label=entity_label))


def tags_for_assignments(config: dict[str, Any], *, key_prefix: str, entity_label: str) -> dict[str, list[dict[str, Any]]]:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
    paths = tag_paths(validated, key_prefix=key_prefix, entity_label=entity_label)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    order = {tag_id: index for index, tag_id in enumerate(ordered_tag_ids(validated, key_prefix=key_prefix, entity_label=entity_label))}
    return {card_key: [{"id": tag_id, "label": tags_by_id[tag_id]["label"], "path": list(paths[tag_id]), "pinned": tag_id in set(validated["pinnedAssignments"].get(card_key, []))} for tag_id in sorted(tag_ids, key=lambda tag_id: order[tag_id])] for card_key, tag_ids in validated["assignments"].items()}


def delete_tag(config: dict[str, Any], tag_id: str, *, key_prefix: str, entity_label: str) -> set[str]:
    validated = validate_tag_config(config, key_prefix=key_prefix, entity_label=entity_label)
    tags_by_id = {tag["id"]: tag for tag in validated["tags"]}
    if tag_id not in tags_by_id:
        raise ValueError(f"标签不存在：{tag_id}")
    children: dict[str | None, list[str]] = {}
    for tag in validated["tags"]:
        children.setdefault(tag["parentId"], []).append(tag["id"])
    removed: set[str] = set()
    pending = [tag_id]
    while pending:
        current = pending.pop()
        removed.add(current)
        pending.extend(children.get(current, []))
    for field in ("assignments", "pinnedAssignments"):
        validated[field] = {card_key: [assigned_id for assigned_id in tag_ids if assigned_id not in removed] for card_key, tag_ids in validated[field].items()}
        validated[field] = {card_key: tag_ids for card_key, tag_ids in validated[field].items() if tag_ids}
    validated["tags"] = [tag for tag in validated["tags"] if tag["id"] not in removed]
    config.clear()
    config.update(validate_tag_config(validated, key_prefix=key_prefix, entity_label=entity_label))
    return removed
