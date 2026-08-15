"""Read official Live A Hero Simplified Chinese texts from a local game snapshot."""

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_SNAPSHOT_DIR = ROOT / "data" / "cache" / "lah-localization"


@dataclass(frozen=True)
class OfficialTexts:
    card_names: dict[str, str]
    skill_texts: dict[str, tuple[str, str]]

    def card_name(self, card_id: str) -> str | None:
        return self.card_names.get(str(card_id))

    def skill_text(self, skill_id: str) -> tuple[str, str] | None:
        return self.skill_texts.get(str(skill_id))


def load_official_texts(source_dir: Path = DEFAULT_SNAPSHOT_DIR) -> OfficialTexts:
    snapshot_files = _snapshot_files(source_dir)
    if snapshot_files is None:
        return OfficialTexts(card_names={}, skill_texts={})

    localized_file, card_master_file, skill_master_file = snapshot_files
    localized = _load_json(localized_file)
    cards = _load_json(card_master_file)
    skills = _load_json(skill_master_file)

    card_names = {}
    for card in _entries(cards):
        card_id = card.get("heroCardId")
        resource_name = card.get("resourceName")
        if card_id is None or not resource_name:
            continue
        name = localized.get(f"CARD_NAME_{resource_name.upper()}")
        if name:
            card_names[str(card_id)] = name

    skill_texts = {}
    for skill in _entries(skills):
        skill_id = skill.get("skillId")
        if skill_id is None:
            continue
        key = str(skill_id)
        name = localized.get(f"SKILL_NAME_{key}", "")
        description = localized.get(f"SKILL_DESCRIPTION_{key}", "")
        if name or description:
            skill_texts[key] = (name, description)

    return OfficialTexts(card_names=card_names, skill_texts=skill_texts)


def load_snapshot_masters(source_dir: Path = DEFAULT_SNAPSHOT_DIR) -> tuple[dict, dict] | None:
    snapshot_files = _snapshot_files(source_dir)
    if snapshot_files is None:
        return None
    _, card_master_file, skill_master_file = snapshot_files
    return _load_json(card_master_file), _load_json(skill_master_file)


def _snapshot_files(source_dir: Path) -> tuple[Path, Path, Path] | None:
    if not source_dir.exists():
        return None
    localized = {
        path.name.removeprefix("ChineseSimplified-").removesuffix(".json"): path
        for path in source_dir.glob("ChineseSimplified-*.json")
    }
    cards = {
        path.name.removeprefix("CardMaster-"): path
        for path in source_dir.glob("CardMaster-*")
    }
    skills = {
        path.name.removeprefix("SkillMaster-"): path
        for path in source_dir.glob("SkillMaster-*")
    }
    snapshot_ids = localized.keys() & cards.keys() & skills.keys()
    if not snapshot_ids:
        return None
    snapshot_id = max(snapshot_ids, key=lambda key: localized[key].stat().st_mtime)
    return localized[snapshot_id], cards[snapshot_id], skills[snapshot_id]


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _entries(data: dict) -> list[dict]:
    return list(data.values()) if isinstance(data, dict) else data
