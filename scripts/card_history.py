"""Attach evidenced release records to the quick-reference catalog."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEFAULT_CARD_HISTORY_PATH = Path(__file__).parent.parent / "data" / "card_history.json"


def _checked_date(value: Any, location: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{location}: expected YYYY-MM-DD or null") from None
    if parsed.isoformat() != value:
        raise ValueError(f"{location}: expected YYYY-MM-DD or null")
    return value


def _checked_record(record: Any, location: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"{location}: expected a record object")
    result = dict(record)
    result["date"] = _checked_date(record.get("date"), f"{location}.date")
    for field in ("version", "context", "note", "versionNote", "description", "title"):
        if record.get(field) is not None and not isinstance(record[field], str):
            raise ValueError(f"{location}.{field}: expected text or null")
    result.setdefault("version", None)
    result.setdefault("context", "")
    sources = record.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(f"{location}.sources: expected a list")
    result["sources"] = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("label"), str):
            raise ValueError(f"{location}.sources: expected label and HTTP(S) URL")
        url = source.get("url")
        try:
            parsed = urlsplit(url) if isinstance(url, str) else None
        except ValueError:
            parsed = None
        if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"{location}.sources: expected label and HTTP(S) URL")
        result["sources"].append({"label": source["label"], "url": url})
    return result


def _read_history(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"schemaVersion": 1, "verifiedAt": None, "cards": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("card history: unsupported schemaVersion")
    data["verifiedAt"] = _checked_date(data.get("verifiedAt"), "card history.verifiedAt")
    if not isinstance(data.get("cards"), dict):
        raise ValueError("card history.cards: expected an object")
    records = {}
    for key, entry in data["cards"].items():
        parts = key.split(":")
        if len(parts) != 2 or parts[0] not in ("hero", "sidekick") or not parts[1].isdigit():
            raise ValueError(f"card history key {key!r}: expected kind:stockId")
        if not isinstance(entry, dict) or not isinstance(entry.get("events", []), list):
            raise ValueError(f"card history.{key}: expected release and events")
        release = entry.get("release")
        events = []
        for index, event in enumerate(entry.get("events", [])):
            checked = _checked_record(event, f"card history.{key}.events[{index}]")
            if checked.get("type") != "tree":
                raise ValueError(f"card history.{key}.events[{index}]: expected type tree")
            events.append(checked)
        records[key] = {
            "release": _checked_record(release, f"card history.{key}.release") if release is not None else None,
            "events": events,
        }
    return {**data, "cards": records}


def attach_card_history(
    catalog: dict[str, Any],
    hero_raw: dict[str, Any],
    sidekick_raw: dict[str, Any],
    history_path: Path | None = DEFAULT_CARD_HISTORY_PATH,
) -> None:
    """Enrich catalog cards in place; missing evidence remains explicitly unknown.

    Records use stock IDs, while family links retain the catalog's selected-card
    keys. Character IDs keep Xeno characters separate from their counterparts.
    """
    data = _read_history(history_path)
    families: dict[str, list[dict[str, Any]]] = {}
    for card in catalog["cards"]:
        raw_cards = hero_raw if card["kind"] == "hero" else sidekick_raw
        raw = raw_cards.get(str(card["cardId"]), {})
        character_id = raw.get("characterId")
        stock_id = raw.get("stockId")
        card["characterId"] = str(character_id) if character_id is not None else None
        card["variantId"] = str(stock_id) if stock_id is not None else None
        evidence = data["cards"].get(f"{card['kind']}:{stock_id}", {})
        if card["kind"] == "sidekick":
            variant_kind = "sidekick"
        elif "カスタム" in raw.get("cardName", ""):
            variant_kind = "custom"
        elif "soldier" in raw.get("resourceName", "").lower():
            variant_kind = "soldier"
        else:
            variant_kind = "unknown"
        card["history"] = {
            "release": evidence.get("release"),
            "events": evidence.get("events", []),
            "familyCardKeys": [card["key"]],
            "baseCardKey": None,
            "variantKind": variant_kind,
            "daysFromBase": None,
        }
        if character_id is not None:
            families.setdefault(str(character_id), []).append(card)

    for family in families.values():
        family.sort(key=lambda card: (int(card["variantId"] or 0), card["kind"], card["key"]))
        heroes = [card for card in family if card["kind"] == "hero"
                  and card["history"]["variantKind"] == "unknown" and card["variantId"]]
        base = heroes[0] if heroes else None
        base_release = base["history"]["release"] if base else None
        base_date = base_release.get("date") if base_release else None
        for card in family:
            history = card["history"]
            history["familyCardKeys"] = [relative["key"] for relative in family]
            history["baseCardKey"] = base["key"] if base else None
            if card in heroes:
                history["variantKind"] = "base" if card is base else "sp"
                release_date = (history["release"] or {}).get("date")
                if card is not base and base_date and release_date:
                    history["daysFromBase"] = (date.fromisoformat(release_date) - date.fromisoformat(base_date)).days

    catalog.setdefault("metadata", {})["cardHistory"] = {
        "schemaVersion": 1,
        "verifiedAt": data["verifiedAt"],
        "recordCount": len(data["cards"]),
        "releaseCount": sum(bool((card["history"]["release"] or {}).get("date")) for card in catalog["cards"]),
        "eventCount": sum(len(card["history"]["events"]) for card in catalog["cards"]),
    }
