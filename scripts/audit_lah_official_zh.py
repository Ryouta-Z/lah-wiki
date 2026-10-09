"""Read-only localization delta and Japanese-to-official-Chinese review candidates."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean(value):
    text = re.sub(r'<br\s*/?>|<style=["\']改行["\']></style>', "\n", str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()


def kana(value):
    return bool(re.search(r"[ぁ-ゖァ-ヺ]", clean(value)))


def chinese(value, japanese=""):
    text = clean(value)
    return bool(re.search(r"[\u3400-\u9fff]", text)) and not kana(text) and text != clean(japanese)


def nested_skills(value):
    if isinstance(value, dict):
        if "skillId" in value and "name" in value and "description" in value:
            yield value
        else:
            for child in value.values():
                yield from nested_skills(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_skills(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = [args.baseline, args.cache_dir / "ChineseSimplified.json", args.cache_dir / "SkillMaster",
             args.cache_dir / "CardMaster", args.cache_dir / "SidekickMaster",
             ROOT / "data/lah_data.json", ROOT / "data/wiki_local.json", ROOT / "data/quickref_catalog.json"]
    sources = [{"path": str(p.resolve()), "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    old, new, skills, heroes, assistants, lah, local, quick = map(read, paths)
    changes = [{"key": key, "kind": "added" if key not in old else "deleted" if key not in new else "changed",
                "old": old.get(key), "new": new.get(key)} for key in sorted(set(old) | set(new))
               if key not in old or key not in new or old[key] != new[key]]
    candidates, manual = [], []

    def compare(owner, sid, entry, source):
        master = skills.get(str(sid), {})
        for field, keypart, jafield in [("name", "NAME", "skillName"), ("description", "DESCRIPTION", "description")]:
            key = f"SKILL_{keypart}_{sid}"
            current, ja, zh = clean(entry.get(field)), clean(master.get(jafield)), clean(new.get(key))
            if not current or not chinese(zh, ja) or not (kana(current) or current == ja) or current == zh:
                continue
            row = {"owner": owner, "source": source, "skillId": str(sid), "field": field,
                   "key": key, "current": current, "official": zh, "japanese": ja,
                   "officialRaw": new[key], "baselineRaw": old.get(key),
                   "newThisRound": key not in old or old.get(key) != new[key], "status": "pending_user_review"}
            if field == "description" and "追加效果" in current:
                row["reason"] = "正文含独立追加效果；主装备官中不能覆盖整个合并描述。"
                manual.append(row)
            else:
                candidates.append(row)

    effective = dict(local)
    effective.update(lah)  # Matches the Wiki bot's actual load precedence.
    for key, entry in effective.items():
        if re.fullmatch(r"skill:\d+", key):
            compare({"key": key, "name": entry.get("name")}, key.split(":")[1],
                    {"name": entry.get("name"), "description": entry.get("content")}, "Wiki机器人查询库")
    for card in quick["cards"]:
        master = (heroes if card["kind"] == "hero" else assistants).get(str(card["cardId"]), {})
        owner = {"key": card["key"], "name": card["name"], "kind": card["kind"],
                 "resourceName": master.get("resourceName"), "cardId": card["cardId"]}
        resource = master.get("resourceName", "").upper()
        namekey = "CARD_NAME_" + resource
        if kana(card["name"]) and chinese(new.get(namekey), master.get("cardName")):
            candidates.append({"owner": owner, "source": "当前速查", "field": "cardName", "key": namekey,
                               "current": card["name"], "official": clean(new[namekey]),
                               "japanese": master.get("cardName"), "officialRaw": new[namekey],
                               "baselineRaw": old.get(namekey), "newThisRound": old.get(namekey) != new[namekey],
                               "status": "pending_user_review"})
        for entry in nested_skills([card["skills"], card.get("skillUpgrades", [])]):
            compare(owner, entry["skillId"], entry, "当前速查")
    for term in quick["statusTerms"]:
        for field, suffix in [("name", "NAME"), ("description", "DESCRIPTION")]:
            if not kana(term.get(field)):
                continue
            matches = [(p + suffix + "_" + term["id"], clean(new.get(p + suffix + "_" + term["id"])))
                       for p in ["OVERRIDE_STATUS_", "STATUS_"]]
            matches = [(k, text) for k, text in matches if chinese(text)]
            if len(matches) == 1:
                key, zh = matches[0]
                candidates.append({"owner": {"key": "status:" + term["id"], "name": term["name"]},
                                   "source": "当前速查机制", "field": field, "key": key,
                                   "current": clean(term[field]), "official": zh, "officialRaw": new[key],
                                   "baselineRaw": old.get(key), "newThisRound": old.get(key) != new[key],
                                   "status": "pending_user_review"})
    unique = {(r["source"], r["owner"]["key"], r["key"]): r for r in candidates}
    candidates = list(unique.values())
    core = [r for r in changes if r["key"].startswith(("CARD_NAME_", "SKILL_NAME_", "SKILL_DESCRIPTION_", "STATUS_", "OVERRIDE_STATUS_"))]
    report = {"schemaVersion": 1, "checkedAtBeijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "sources": sources, "oldKeyCount": len(old), "newKeyCount": len(new),
              "deltaCounts": {kind: sum(r["kind"] == kind for r in changes) for kind in ["added", "changed", "deleted"]},
              "coreDeltaCount": len(core),
              "changes": changes, "newChineseTextCandidates": [r for r in changes if chinese(r.get("new"))],
              "replacementCandidates": candidates, "manualCompositeDescriptions": manual,
              "candidateSkillIds": sorted({r["skillId"] for r in candidates if "skillId" in r}),
              "scope": "全量字典差异；当前Wiki机器人查询条目、速查卡片/强化技能/机制中的日文残留。已为中文的改写或漏句需另作语义审核。",
              "caution": "语言识别是候选筛选，不自动批准译文；旧键已存在的官中不得称本轮新增。复用缓存检查时间不代表服务器上传或游戏实装时间。",
              "formalWikiModified": False, "status": "pending_user_review"}
    for source in sources:
        assert hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() == source["sha256"]
    target = args.output_dir / "audit.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(target), "delta": report["deltaCounts"], "coreDeltaCount": len(core),
                      "candidateFields": len(candidates), "candidateSkillIds": report["candidateSkillIds"],
                      "manualCompositeDescriptions": len(manual)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
