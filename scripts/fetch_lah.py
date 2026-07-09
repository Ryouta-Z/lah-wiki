"""下载 Live A Hero 社区数据库，合并英雄+技能，生成本地查询数据。

数据源: https://github.com/liveahero-community/translations (开源, 无反爬)
用法: uv run python scripts/fetch_lah.py
"""
import json
import sys
from pathlib import Path

import httpx

REPO_RAW = "https://raw.githubusercontent.com/liveahero-community/translations/main/"
API_TREE = "https://api.github.com/repos/liveahero-community/translations/git/trees/main?recursive=1"
UA = {"User-Agent": "LW-WIKI-Bot/0.1"}

OUT_FILE = Path(__file__).parent.parent / "data" / "lah_data.json"


def http_get(path: str, retries: int = 3) -> httpx.Response:
    last = None
    for i in range(retries):
        try:
            return httpx.get(REPO_RAW + path, headers=UA, timeout=120.0)
        except httpx.HTTPError as e:
            last = e
            print(f"  下载 {path} 失败({i+1}/{retries}): {type(e).__name__}, 重试...")
    raise last


def latest_version() -> int:
    resp = httpx.get(API_TREE, headers=UA, timeout=30)
    resp.raise_for_status()
    files = [t["path"] for t in resp.json().get("tree", []) if t["type"] == "blob"]
    versions = {
        int(f.split("/")[1])
        for f in files
        if f.startswith("master-data/") and f.split("/")[1].isdigit()
    }
    return max(versions)


def load_tsv(path: str) -> dict:
    """解析 id \t name \t desc 形式的翻译表, 返回 {id: (name, desc)}。"""
    resp = http_get(path)
    if resp.status_code != 200:
        return {}
    result = {}
    for line in resp.text.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2 and cols[0].strip():
            key = cols[0].strip()
            name = cols[1].strip()
            desc = cols[2].strip() if len(cols) >= 3 else ""
            result[key] = (name, desc)
    return result


def build(ver: int):
    print("下载英雄数据 CardMaster...")
    cards = http_get(f"master-data/{ver}/ja-JP/CardMaster.json").json()
    print("下载技能数据 SkillMaster...")
    skills_raw = http_get(f"master-data/{ver}/ja-JP/SkillMaster.json").json()
    print("下载中文翻译...")
    hero_tr = load_tsv("translations/zh-CN/heroes.tsv")
    skill_tr = load_tsv("translations/zh-CN/skills.tsv")

    skills = _index(skills_raw)
    cards_idx = _index(cards)

    entries = {}
    _build_skills(entries, skills, skill_tr)
    _build_heroes(entries, cards_idx, skills, hero_tr, skill_tr)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    print(f"完成: {len(entries)} 条 -> {OUT_FILE}")


def _build_heroes(entries, cards, skills, hero_tr, skill_tr):
    seen = set()
    count = 0
    for hid, card in cards.items():
        name, _ = _pick(hero_tr, hid, card.get("cardName", ""), "")
        if not name or name in seen:
            continue
        seen.add(name)
        skill_names = []
        for skid in card.get("skillIds", []):
            sk = skills.get(str(skid))
            if not sk:
                continue
            sn, _ = _pick(skill_tr, str(skid), sk.get("skillName", ""), "")
            if sn:
                skill_names.append(sn)
        rarity = "★" * card.get("rarity", 0)
        content = f"稀有度: {rarity or '?'}\n技能: {'、'.join(skill_names) or '无'}"
        entries[f"hero:{hid}"] = {
            "name": name, "type": "英雄",
            "aliases": [card.get("cardName", "")] if card.get("cardName") != name else [],
            "content": content,
        }
        count += 1
    print(f"  英雄: {count} 条")


def _pick(tr: dict, sid: str, fallback_name: str, fallback_desc: str):
    """优先取中文翻译, 缺失时回退日文原文。"""
    if sid in tr and tr[sid][0]:
        name = tr[sid][0]
        desc = tr[sid][1] or fallback_desc
        return name, desc
    return fallback_name, fallback_desc


def _build_skills(entries: dict, skills: dict, skill_tr: dict):
    count = 0
    for sid, sk in skills.items():
        if not sk.get("isHeroSkill"):
            continue
        name, desc = _pick(skill_tr, sid, sk.get("skillName", ""), sk.get("description", ""))
        if not name:
            continue
        entries[f"skill:{sid}"] = {
            "name": name,
            "type": "技能",
            "aliases": [sk.get("skillName", "")] if sk.get("skillName") != name else [],
            "content": _clean(desc) or "（暂无描述）",
        }
        count += 1
    print(f"  英雄技能: {count} 条")


def _index(data) -> dict:
    """把 list 或 dict 形式的 master 数据统一成 {str(id): entry}。"""
    result = {}
    items = data.values() if isinstance(data, dict) else data
    for entry in items:
        key = entry.get("skillId", entry.get("heroCardId"))
        if key is not None:
            result[str(key)] = entry
    return result


def _clean(text: str) -> str:
    """移除游戏描述里的排版标记, 如 <style ...></style>。"""
    import re
    text = re.sub(r"<style[^>]*>.*?</style>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def main():
    print("查询最新版本...")
    ver = latest_version()
    print(f"最新版本: {ver}")
    build(ver)


if __name__ == "__main__":
    main()
