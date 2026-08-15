"""下载 Live A Hero 社区数据库，合并英雄+技能，生成本地查询数据。

数据源: https://github.com/liveahero-community/translations (开源, 无反爬)
用法: uv run python scripts/fetch_lah.py
"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from official_lah import OfficialTexts, load_official_texts, load_snapshot_masters

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

    _build_entries(cards, skills_raw, hero_tr, skill_tr)


def build_from_snapshot():
    snapshot = load_snapshot_masters()
    if snapshot is None:
        raise RuntimeError("本地官方数据快照不完整，无法离线生成")
    cards, skills_raw = snapshot
    print("使用本地官方 CardMaster、SkillMaster 和简中表生成数据...")
    _build_entries(cards, skills_raw, {}, {}, allow_network_translation=False)


def _build_entries(
    cards, skills_raw, hero_tr, skill_tr, allow_network_translation: bool = True
):
    skills = _index(skills_raw)
    cards_idx = _index(cards)
    official = load_official_texts()

    mtl_map = _machine_translate(
        skills, skill_tr, official, allow_network_translation=allow_network_translation
    )

    entries = {}
    _build_skills(entries, skills, skill_tr, official, mtl_map)
    _build_heroes(entries, cards_idx, skills, hero_tr, skill_tr, official, mtl_map)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    print(f"完成: {len(entries)} 条 -> {OUT_FILE}")


def _build_heroes(entries, cards, skills, hero_tr, skill_tr, official, mtl_map):
    seen = set()
    count = 0
    for hid, card in cards.items():
        name = official.card_name(hid) or _pick(
            hero_tr, hid, card.get("cardName", ""), ""
        )[0]
        if not name or name in seen:
            continue
        seen.add(name)
        skill_lines = []
        for skid in card.get("skillIds", []):
            sk = skills.get(str(skid))
            if not sk:
                continue
            official_name, official_desc = official.skill_text(skid) or ("", "")
            sn = official_name or _pick(
                skill_tr, str(skid), sk.get("skillName", ""), sk.get("description", "")
            )[0]
            if not sn:
                continue
            desc = _resolve_desc(
                skill_tr, str(skid), sk.get("description", ""), official_desc, mtl_map
            )
            if desc:
                skill_lines.append(f"· {sn}\n  {desc}")
            else:
                skill_lines.append(f"· {sn}")
        rarity = "★" * card.get("rarity", 0)
        skills_text = "\n".join(skill_lines) if skill_lines else "无"
        content = f"稀有度: {rarity or '?'}\n【技能】\n{skills_text}"
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


def _looks_cn(text: str) -> bool:
    """不含平假名/片假名即视为中文(假名是日文独有, 中文不会出现)。"""
    import re
    if not text:
        return False
    return not re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text)


def _has_cn_desc(tr: dict, sid: str) -> bool:
    """社区表里存在且确实是中文(而非日文原文)。"""
    return bool(tr.get(sid) and tr[sid][1] and _looks_cn(tr[sid][1]))


def _machine_translate(
    skills: dict,
    skill_tr: dict,
    official: OfficialTexts,
    allow_network_translation: bool = True,
) -> dict:
    """收集缺少中文的日文技能描述, 用 Edge 免费翻译补齐。返回 {日文原文: 中文}。"""
    from mtl import Translator

    need = []
    for sid, sk in skills.items():
        official_text = official.skill_text(sid)
        if official_text and official_text[1]:
            continue
        if _has_cn_desc(skill_tr, sid):
            continue
        jp = _clean(sk.get("description", ""))
        if jp:
            need.append(jp)
    if not need:
        return {}
    translator = Translator()
    if not allow_network_translation:
        return {text: translator.cache[text] for text in need if text in translator.cache}
    print(f"机器翻译日文技能描述({len(set(need))} 条唯一)...")
    try:
        return translator.translate_all(need)
    except (RuntimeError, httpx.HTTPError):
        print("机器翻译不可用，使用已有翻译缓存，其余保留日文原文。")
        return {text: translator.cache[text] for text in need if text in translator.cache}


def _resolve_desc(skill_tr, sid, jp_desc, official_desc, mtl_map):
    """技能描述: 官方中文 > 社区中文 > 机翻中文 > 日文原文。"""
    jp = _clean(jp_desc)
    if official_desc:
        return _clean(official_desc)
    if _has_cn_desc(skill_tr, sid):
        return _clean(skill_tr[sid][1])
    cn = mtl_map.get(jp)
    return cn or jp


def _build_skills(
    entries: dict, skills: dict, skill_tr: dict, official: OfficialTexts, mtl_map: dict
):
    count = 0
    for sid, sk in skills.items():
        if not sk.get("isHeroSkill"):
            continue
        official_name, official_desc = official.skill_text(sid) or ("", "")
        name = official_name or _pick(
            skill_tr, sid, sk.get("skillName", ""), sk.get("description", "")
        )[0]
        if not name:
            continue
        desc = _resolve_desc(skill_tr, sid, sk.get("description", ""), official_desc, mtl_map)
        entries[f"skill:{sid}"] = {
            "name": name,
            "type": "技能",
            "aliases": [sk.get("skillName", "")] if sk.get("skillName") != name else [],
            "content": desc or "（暂无描述）",
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
    try:
        ver = latest_version()
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 403:
            raise
        print("GitHub API 限流，改用本地官方数据快照。")
        build_from_snapshot()
        return
    print(f"最新版本: {ver}")
    build(ver)


if __name__ == "__main__":
    main()
