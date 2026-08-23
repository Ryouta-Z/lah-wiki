"""Build an offline Live A Hero hero/sidekick quick-reference catalog."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).parent.parent
DEFAULT_SNAPSHOT_DIR = ROOT / "data" / "cache" / "lah-localization"
DEFAULT_CATALOG_PATH = ROOT / "data" / "quickref_catalog.json"
DEFAULT_SITE_PATH = ROOT / "quickref" / "index.html"
DEFAULT_ALIASES_PATH = ROOT / "data" / "aliases.json"
CODEX_NODE_PATH = Path(
    r"C:\Users\Penguin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)

ELEMENT_LABELS = {1: "火", 2: "水", 3: "木", 4: "光", 5: "暗"}
ROLE_LABELS = {
    0: "无",
    1: "攻击",
    2: "防御",
    3: "辅助",
    4: "弱化",
    5: "速度操控",
    6: "View 获取",
    7: "回复",
    99: "特殊",
}


def build_catalog(
    snapshot_dir: Path, aliases_path: Path = DEFAULT_ALIASES_PATH
) -> dict[str, Any]:
    """Return a normalized catalog from one complete, date-consistent snapshot."""
    snapshot = _snapshot_files(snapshot_dir)
    localized = _read_json(snapshot["localized"])
    hero_cards = _read_json(snapshot["hero_cards"])
    sidekick_cards = _read_json(snapshot["sidekick_cards"])
    skills = _index_by_id(_read_json(snapshot["skills"]), "skillId")
    aliases = _aliases_by_original(_read_json(aliases_path)) if aliases_path.exists() else {}

    cards = [
        *_build_cards(hero_cards, skills, localized, aliases, "hero"),
        *_build_cards(sidekick_cards, skills, localized, aliases, "sidekick"),
    ]
    cards.sort(key=lambda card: (card["kind"], card["name"], card["cardId"]))

    skill_rows = _unique_skills(cards)
    return {
        "metadata": {
            "snapshotId": snapshot["id"],
            "generatedAt": datetime.now(UTC).isoformat(),
            "heroCardCount": sum(card["kind"] == "hero" for card in cards),
            "sidekickCardCount": sum(card["kind"] == "sidekick" for card in cards),
            "skillCount": len(skill_rows),
            "translationPolicy": "仅官方简中；缺失项保留日文原文。",
        },
        "cards": cards,
        "skills": skill_rows,
    }


def write_catalog(catalog: dict[str, Any], output_path: Path) -> None:
    _write_json_atomic(output_path, catalog)


def write_static_site(catalog: dict[str, Any], output_path: Path) -> None:
    _write_text_atomic(output_path, render_static_html(catalog))


def render_static_html(catalog: dict[str, Any]) -> str:
    embedded_catalog = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live A Hero 本地速查</title>
  <style>
    :root {{ color-scheme: dark; font-family: "Microsoft YaHei UI", system-ui, sans-serif; background: #101827; color: #e6edf8; }}
    * {{ box-sizing: border-box; }} body {{ margin: 0; min-width: 320px; }}
    header {{ padding: 34px max(20px, calc((100vw - 1180px) / 2)); background: linear-gradient(130deg, #1d4ed8, #7c3aed); }}
    h1 {{ margin: 0; font-size: clamp(25px, 4vw, 38px); }} header p {{ color: #dbeafe; margin: 10px 0 0; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 24px auto 52px; }}
    .controls {{ display: grid; grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(110px, 1fr)); gap: 12px; }}
    input, select {{ width: 100%; border: 1px solid #394867; border-radius: 9px; background: #172235; color: #edf2ff; padding: 12px; font: inherit; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; color: #b9c7df; }} .pill {{ padding: 6px 10px; border-radius: 999px; background: #1f2c43; }}
    .groups {{ display: grid; gap: 28px; }} h2 {{ margin: 0 0 10px; font-size: 22px; }} .results {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }}
    button.card {{ cursor: pointer; text-align: left; border: 1px solid #31425f; border-radius: 12px; color: inherit; padding: 15px; background: #162238; font: inherit; }} button.card:hover, button.card:focus {{ border-color: #77a5ff; background: #1b2c49; }}
    .card-title {{ display: flex; justify-content: space-between; gap: 8px; font-weight: 700; }} .muted {{ color: #a9b7cf; font-size: 13px; }} .tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }} .tag {{ background: #293b59; border-radius: 5px; padding: 3px 7px; font-size: 12px; }}
    dialog {{ width: min(820px, calc(100% - 28px)); max-height: 88vh; overflow: auto; color: #edf2ff; background: #132038; border: 1px solid #516a93; border-radius: 14px; padding: 0; }} dialog::backdrop {{ background: rgb(0 0 0 / 65%); }}
    .detail {{ padding: 24px; }} .close {{ float: right; cursor: pointer; color: #dce8ff; background: transparent; border: 0; font-size: 26px; }} .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 9px; margin: 18px 0; }} .stat {{ background: #1c2b46; padding: 10px; border-radius: 8px; }} .skill {{ border-left: 3px solid #7aa6ff; background: #192942; padding: 12px; margin: 10px 0; white-space: pre-wrap; }} .source {{ color: #fbbf24; font-size: 12px; margin-top: 6px; }}
    .empty {{ color: #a9b7cf; margin: 20px 0; }} @media (max-width: 850px) {{ .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .controls input {{ grid-column: span 2; }} }}
  </style>
</head>
<body>
  <header><h1>Live A Hero 本地速查</h1><p id="snapshot"></p></header>
  <main>
    <section class="controls" aria-label="筛选条件">
      <input id="query" autofocus placeholder="搜索中文名、日文名、卡片编号或技能内容，例如：阿卡西">
      <select id="kind"><option value="">英雄与助手</option><option value="hero">仅英雄</option><option value="sidekick">仅助手</option></select>
      <select id="rarity"><option value="">全部稀有度</option></select>
      <select id="element"><option value="">全部元素</option></select>
      <select id="role"><option value="">全部定位</option></select>
    </section>
    <p class="summary" id="summary"></p><div class="groups" id="groups"></div>
  </main>
  <dialog id="detail"><div class="detail"><button class="close" aria-label="关闭">×</button><div id="detailContent"></div></div></dialog>
  <script>
    const catalog = {embedded_catalog};
    const cards = catalog.cards;
    const byId = new Map(cards.map(card => [card.key, card]));
    const $ = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    const kindLabel = kind => kind === 'hero' ? '英雄' : '助手';
    function options(id, values) {{
      for (const value of [...values].filter(Boolean).sort((a,b) => String(a).localeCompare(String(b), 'zh-CN'))) {{
        const option = document.createElement('option'); option.value = value; option.textContent = value; $(id).append(option);
      }}
    }}
    options('rarity', new Set(cards.map(card => '★'.repeat(card.rarity))));
    options('element', new Set(cards.map(card => card.element?.label)));
    options('role', new Set(cards.map(card => card.role.label)));
    $('snapshot').textContent = `快照：${{catalog.metadata.snapshotId}} · 英雄 ${{catalog.metadata.heroCardCount}} 张 · 助手 ${{catalog.metadata.sidekickCardCount}} 张 · ${{catalog.metadata.translationPolicy}}`;
    function matches(card) {{
      const query = $('query').value.trim().toLocaleLowerCase();
      const haystack = [card.name, card.originalName, card.cardId, ...card.aliases, ...card.skills.flatMap(skill => [skill.name, skill.originalName, skill.description])].join('\\n').toLocaleLowerCase();
      return (!query || haystack.includes(query)) && (!$('kind').value || card.kind === $('kind').value) && (!$('rarity').value || '★'.repeat(card.rarity) === $('rarity').value) && (!$('element').value || card.element?.label === $('element').value) && (!$('role').value || card.role.label === $('role').value);
    }}
    function render() {{
      const result = cards.filter(matches); const groups = $('groups'); groups.replaceChildren();
      $('summary').textContent = `找到 ${{result.length}} 张卡；输入角色名会按英雄和助手分组。`;
      for (const kind of ['hero', 'sidekick']) {{
        const list = result.filter(card => card.kind === kind); if (!list.length) continue;
        const section = document.createElement('section'); const heading = document.createElement('h2'); heading.textContent = `${{kindLabel(kind)}}（${{list.length}}）`; section.append(heading);
        const grid = document.createElement('div'); grid.className = 'results';
        for (const card of list) {{ const button = document.createElement('button'); button.className='card'; button.dataset.key=card.key; button.innerHTML = `<div class="card-title"><span>${{escape(card.name)}}</span><span>${{escape('★'.repeat(card.rarity))}}</span></div><div class="muted">${{escape(card.originalName)}} · #${{escape(card.cardId)}}</div><div class="tags"><span class="tag">${{escape(card.element?.label || '无元素')}}</span><span class="tag">${{escape(card.role.label)}}</span><span class="tag">技能 ${{card.skills.length}}</span></div>`; grid.append(button); }}
        section.append(grid); groups.append(section);
      }}
      if (!result.length) groups.innerHTML = '<p class="empty">没有匹配项。可尝试角色日文名、卡片编号或技能文字。</p>';
    }}
    function showDetail(card) {{
      const stats = [['稀有度','★'.repeat(card.rarity)], ['元素',card.element?.label || '不适用'], ['定位',card.role.label], ['1级 HP',card.stats.level1.hp], ['1级 攻击',card.stats.level1.attack], ['1级 速度',card.stats.level1.agility], ['满级 HP',card.stats.max.hp], ['满级 攻击',card.stats.max.attack], ['满级 速度',card.stats.max.agility]];
      $('detailContent').innerHTML = `<h2>${{escape(kindLabel(card.kind))}} · ${{escape(card.name)}}</h2><p class="muted">${{escape(card.originalName)}} · 卡片编号 #${{escape(card.cardId)}}</p><div class="stat-grid">${{stats.map(([label,value]) => `<div class="stat"><div class="muted">${{label}}</div><strong>${{escape(value ?? '—')}}</strong></div>`).join('')}}</div><h3>关联技能</h3>${{card.skills.map(skill => `<article class="skill"><strong>${{escape(skill.relation)}} · ${{escape(skill.name)}}</strong><div class="muted">${{escape(skill.originalName)}} · #${{escape(skill.skillId)}}</div><div>${{escape(skill.description)}}</div>${{skill.nameSource === '日文原文' || skill.descriptionSource === '日文原文' ? '<div class="source">日文原文（官方简中未覆盖）</div>' : ''}}</article>`).join('')}}`;
      $('detail').showModal();
    }}
    document.addEventListener('input', event => {{ if (event.target.matches('input,select')) render(); }});
    document.addEventListener('change', event => {{ if (event.target.matches('select')) render(); }});
    document.addEventListener('click', event => {{ const button = event.target.closest('button.card'); if (button) showDetail(byId.get(button.dataset.key)); }});
    document.querySelector('.close').addEventListener('click', () => $('detail').close());
    render();
  </script>
</body>
</html>"""


def _build_cards(
    raw_cards: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    aliases: dict[str, list[str]],
    kind: str,
) -> list[dict[str, Any]]:
    result = []
    entries = raw_cards.values() if isinstance(raw_cards, dict) else raw_cards
    id_field = "heroCardId" if kind == "hero" else "sidekickCardId"
    for raw_card in entries:
        card_id = raw_card.get(id_field)
        if card_id is None:
            raise ValueError(f"{kind} card missing {id_field}: {raw_card}")
        resource_name = raw_card.get("resourceName", "")
        original_name = raw_card.get("cardName", resource_name or str(card_id))
        localized_name = localized.get(f"CARD_NAME_{resource_name.upper()}") if resource_name else None
        name = localized_name or original_name
        active_ids = raw_card.get("skillIds") or []
        equipment_ids = raw_card.get("equipmentSkills") or [] if kind == "sidekick" else []
        card_skills = [
            *[_skill_row(skill_id, "主动技能", skills, localized) for skill_id in active_ids],
            *[_skill_row(skill_id, "装备技能", skills, localized) for skill_id in equipment_ids],
        ]
        result.append(
            {
                "key": f"{kind}:{card_id}",
                "kind": kind,
                "cardId": str(card_id),
                "name": name,
                "nameSource": "官方简中" if localized_name else "日文原文",
                "originalName": original_name,
                "aliases": aliases.get(original_name, []),
                "rarity": raw_card.get("rarity", 0),
                "element": _element(raw_card.get("element")) if kind == "hero" else None,
                "role": _role(raw_card.get("role")),
                "stats": _stats(raw_card.get("growths") or []),
                "skills": card_skills,
            }
        )
    return result


def _skill_row(
    skill_id: int | str,
    relation: str,
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
) -> dict[str, Any]:
    raw_skill = skills.get(str(skill_id))
    if raw_skill is None:
        raise ValueError(f"card references missing skill: {skill_id}")
    original_name = raw_skill.get("skillName") or str(skill_id)
    original_description = _clean_text(raw_skill.get("description", ""))
    name = localized.get(f"SKILL_NAME_{skill_id}") or original_name
    description = localized.get(f"SKILL_DESCRIPTION_{skill_id}") or original_description
    return {
        "skillId": str(skill_id),
        "relation": relation,
        "name": name,
        "nameSource": "官方简中" if localized.get(f"SKILL_NAME_{skill_id}") else "日文原文",
        "originalName": original_name,
        "description": _clean_text(description),
        "descriptionSource": "官方简中"
        if localized.get(f"SKILL_DESCRIPTION_{skill_id}")
        else "日文原文",
    }


def _unique_skills(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {}
    for card in cards:
        for skill in card["skills"]:
            indexed.setdefault(skill["skillId"], skill)
    return sorted(indexed.values(), key=lambda skill: (skill["name"], skill["skillId"]))


def _aliases_by_original(aliases: dict[str, str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for alias, original_name in aliases.items():
        result.setdefault(original_name, []).append(alias)
    return {key: sorted(values) for key, values in result.items()}


def _element(value: int | None) -> dict[str, Any]:
    return {"code": value, "label": ELEMENT_LABELS.get(value, f"属性代码 {value}")}


def _role(value: int | None) -> dict[str, Any]:
    return {"code": value, "label": ROLE_LABELS.get(value, f"定位代码 {value}")}


def _stats(growths: list[dict[str, Any]]) -> dict[str, Any]:
    if not growths:
        return {"level1": {}, "max": {}}
    ordered = sorted(growths, key=lambda growth: growth.get("level", 0))
    return {"level1": _stat_values(ordered[0]), "max": _stat_values(ordered[-1])}


def _stat_values(growth: dict[str, Any]) -> dict[str, Any]:
    return {"level": growth.get("level"), "hp": growth.get("hp"), "attack": growth.get("attack"), "agility": growth.get("agility")}


def _snapshot_files(snapshot_dir: Path) -> dict[str, Path | str]:
    patterns = {
        "localized": ("ChineseSimplified-", ".json"),
        "hero_cards": ("CardMaster-", ""),
        "sidekick_cards": ("SidekickMaster-", ""),
        "skills": ("SkillMaster-", ""),
    }
    tagged: dict[str, dict[str, Path]] = {}
    for name, (prefix, suffix) in patterns.items():
        tagged[name] = {
            path.name.removeprefix(prefix).removesuffix(suffix): path
            for path in snapshot_dir.glob(f"{prefix}*{suffix}")
            if path.is_file()
        }
    snapshot_ids = set.intersection(*(set(items) for items in tagged.values()))
    if not snapshot_ids:
        raise ValueError(
            "需要同一标签的 ChineseSimplified、CardMaster、SidekickMaster 和 SkillMaster 快照"
        )
    snapshot_id = max(snapshot_ids, key=lambda value: tagged["localized"][value].stat().st_mtime)
    return {"id": snapshot_id, **{name: items[snapshot_id] for name, items in tagged.items()}}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _index_by_id(data: dict[str, Any], id_field: str) -> dict[str, dict[str, Any]]:
    values = data.values() if isinstance(data, dict) else data
    return {str(value[id_field]): value for value in values if value.get(id_field) is not None}


def _clean_text(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(value, ensure_ascii=False, indent=2))


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as file:
        file.write(content)
        temp_path = Path(file.name)
    temp_path.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Live A Hero 离线速查数据与网页")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE_PATH)
    parser.add_argument("--xlsx", type=Path, help="同时导出 Excel 工作簿")
    parser.add_argument(
        "--node",
        default=str(CODEX_NODE_PATH) if CODEX_NODE_PATH.is_file() else shutil.which("node") or "node",
    )
    args = parser.parse_args()
    catalog = build_catalog(args.snapshot_dir)
    write_catalog(catalog, args.catalog)
    write_static_site(catalog, args.site)
    if args.xlsx:
        subprocess.run(
            [
                args.node,
                str(ROOT / "scripts" / "build_quickref_excel.mjs"),
                str(args.catalog),
                str(args.xlsx),
            ],
            check=True,
        )
    print(
        f"已生成快照 {catalog['metadata']['snapshotId']}："
        f"英雄 {catalog['metadata']['heroCardCount']} 张，"
        f"助手 {catalog['metadata']['sidekickCardCount']} 张 -> {args.site}"
    )


if __name__ == "__main__":
    main()
