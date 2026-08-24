"""Build an offline Live A Hero hero/sidekick quick-reference catalog."""

from __future__ import annotations

import argparse
import json
import os
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
DEFAULT_CHAR_MAP_PATH = ROOT / "data" / "char_map.json"
DEFAULT_ICON_DIR = ROOT / "data" / "images" / "icon"
DEFAULT_AVATAR_OVERRIDES_PATH = ROOT / "data" / "quickref_avatar_overrides.json"
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
    snapshot_dir: Path,
    aliases_path: Path = DEFAULT_ALIASES_PATH,
    char_map_path: Path = DEFAULT_CHAR_MAP_PATH,
    icon_dir: Path = DEFAULT_ICON_DIR,
    avatar_overrides_path: Path = DEFAULT_AVATAR_OVERRIDES_PATH,
) -> dict[str, Any]:
    """Return a normalized catalog from one complete, date-consistent snapshot."""
    snapshot = _snapshot_files(snapshot_dir)
    localized = _read_json(snapshot["localized"])
    hero_cards = _read_json(snapshot["hero_cards"])
    sidekick_cards = _read_json(snapshot["sidekick_cards"])
    skills = _index_by_id(_read_json(snapshot["skills"]), "skillId")
    aliases = _aliases_by_original(_read_json(aliases_path)) if aliases_path.exists() else {}
    avatars = _avatar_index(
        _read_json(char_map_path) if char_map_path.exists() else {},
        icon_dir,
        avatar_overrides_path,
    )
    status_terms = _status_terms_by_id(localized)

    cards = [
        *_build_cards(_highest_hero_cards(hero_cards), skills, localized, aliases, avatars, status_terms, "hero"),
        *_build_cards(_highest_sidekick_cards(sidekick_cards), skills, localized, aliases, avatars, status_terms, "sidekick"),
    ]
    cards.sort(key=lambda card: (card["kind"], card["name"], card["cardId"]))

    skill_rows = _unique_skills(cards)
    skill_upgrades = _unique_skill_upgrades(cards)
    return {
        "metadata": {
            "snapshotId": snapshot["id"],
            "generatedAt": datetime.now(UTC).isoformat(),
            "heroCardCount": sum(card["kind"] == "hero" for card in cards),
            "sidekickCardCount": sum(card["kind"] == "sidekick" for card in cards),
            "skillCount": len(skill_rows),
            "skillUpgradeCount": len(skill_upgrades),
            "translationPolicy": "仅官方简中；缺失项保留日文原文。",
            "heroStatPolicy": "同名英雄仅保留最高星卡的 60 级属性；无 60 级数据的特殊卡保留技能并标记。",
            "sidekickSkillPolicy": "每名助手仅保留最高阶段的主动技能与最高等级装备技能。",
        },
        "cards": cards,
        "skills": skill_rows,
        "skillUpgrades": skill_upgrades,
        "statusTerms": sorted(status_terms["all"].values(), key=lambda term: (term["name"], term["id"])),
    }


def write_catalog(catalog: dict[str, Any], output_path: Path) -> None:
    _write_json_atomic(output_path, catalog)


def write_static_site(
    catalog: dict[str, Any], output_path: Path, icon_dir: Path = DEFAULT_ICON_DIR
) -> None:
    avatar_url_prefix = Path(os.path.relpath(icon_dir, start=output_path.parent)).as_posix()
    _write_text_atomic(output_path, render_static_html(catalog, avatar_url_prefix))


def render_static_html(catalog: dict[str, Any], avatar_url_prefix: str = "../data/images/icon") -> str:
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
    .controls {{ display: grid; grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(110px, 1fr)) minmax(220px, 1.7fr) minmax(110px, 1fr); gap: 12px; align-items: end; }}
    input, select, .controls button {{ width: 100%; border: 1px solid #394867; border-radius: 9px; background: #172235; color: #edf2ff; padding: 12px; font: inherit; }} .controls button {{ cursor: pointer; }} .controls button:hover, .controls button:focus {{ border-color: #77a5ff; background: #1b2c49; }}
    .filter-control {{ display: grid; gap: 6px; min-width: 0; }} .control-label {{ color: #b9c7df; font-size: 13px; font-weight: 700; }} .sort-selects {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(82px, auto); }} .sort-selects select {{ border-radius: 0; }} .sort-selects select:first-child {{ border-radius: 9px 0 0 9px; }} .sort-selects select + select {{ border-left: 0; border-radius: 0 9px 9px 0; }} .multi-select {{ position: relative; }} .multi-select-trigger {{ display: flex; justify-content: space-between; align-items: center; text-align: left; }} .multi-select-trigger::after {{ content: '▾'; margin-left: 8px; color: #b9c7df; }} .multi-select-menu {{ position: absolute; z-index: 4; top: calc(100% + 6px); left: 0; width: max-content; min-width: 100%; max-width: min(310px, calc(100vw - 32px)); padding: 8px; border: 1px solid #516a93; border-radius: 9px; background: #132038; box-shadow: 0 12px 32px rgb(0 0 0 / 35%); }} .multi-select-options {{ display: grid; gap: 2px; max-height: 260px; overflow: auto; }} .multi-select-option {{ display: flex; align-items: center; gap: 8px; padding: 7px; border-radius: 6px; cursor: pointer; }} .multi-select-option:hover {{ background: #1b2c49; }} .multi-select-option input {{ width: auto; margin: 0; padding: 0; border: 0; background: transparent; accent-color: #77a5ff; }} .multi-select-clear {{ margin-top: 8px; border-color: #516a93 !important; background: #1c2b46 !important; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; color: #b9c7df; }} .pill {{ padding: 6px 10px; border-radius: 999px; background: #1f2c43; }}
    .groups {{ display: grid; gap: 28px; }} h2 {{ margin: 0 0 10px; font-size: 22px; }} .results {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }}
    button.card {{ cursor: pointer; text-align: left; border: 1px solid #31425f; border-radius: 12px; color: inherit; padding: 15px; background: #162238; font: inherit; }} button.card:hover, button.card:focus {{ border-color: #77a5ff; background: #1b2c49; }} .card-layout {{ display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 12px; align-items: center; }}
    .card-title {{ display: flex; justify-content: space-between; gap: 8px; font-weight: 700; }} .muted {{ color: #a9b7cf; font-size: 13px; }} .tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }} .tag {{ background: #293b59; border-radius: 5px; padding: 3px 7px; font-size: 12px; }}
    .avatar {{ display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #4d6a98; border-radius: 50%; background: #263c60; color: #d8e7ff; font-weight: 700; }} .avatar img {{ width: 100%; height: 100%; object-fit: cover; }} .avatar-small {{ width: 58px; height: 58px; font-size: 24px; }} .avatar-large {{ width: 86px; height: 86px; font-size: 34px; }} .avatar-missing {{ border-style: dashed; color: #b7c8e5; }}
    dialog {{ width: min(820px, calc(100% - 28px)); max-height: 88vh; overflow: auto; color: #edf2ff; background: #132038; border: 1px solid #516a93; border-radius: 14px; padding: 0; }} dialog::backdrop {{ background: rgb(0 0 0 / 65%); }}
    .detail {{ padding: 24px; }} .close {{ float: right; cursor: pointer; color: #dce8ff; background: transparent; border: 0; font-size: 26px; }} .detail-heading {{ display: flex; gap: 16px; align-items: center; padding-right: 34px; }} .detail-heading h2 {{ margin: 0; }} .hero-detail-header {{ position: sticky; top: 0; z-index: 1; display: flex; gap: 16px; align-items: center; width: calc(100% + 48px); margin: -24px -24px 18px; padding: 24px 58px 18px 24px; background: #132038; border-bottom: 1px solid #516a93; box-shadow: 0 5px 12px rgb(8 15 29 / 55%); }} .hero-detail-header .detail-close {{ position: absolute; top: 18px; right: 18px; z-index: 2; }} .hero-detail-header .detail-heading {{ flex: 1 1 280px; min-width: 0; padding-right: 0; }} .hero-detail-facts {{ display: grid; flex: 0 1 250px; grid-template-columns: repeat(2, minmax(105px, 1fr)); gap: 9px; }} .hero-detail-fact {{ min-width: 0; padding: 9px 11px; border-radius: 8px; background: #1c2b46; }} .hero-detail-fact strong {{ display: block; font-size: 22px; }} .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 9px; margin: 18px 0; }} .stat {{ background: #1c2b46; padding: 10px; border-radius: 8px; }} .skill {{ border-left: 3px solid #7aa6ff; background: #192942; padding: 12px; margin: 10px 0; white-space: pre-wrap; }} .upgrade {{ border-left-color: #f59e0b; }} .source {{ color: #fbbf24; font-size: 12px; margin-top: 6px; }}
    .status-detail {{ position: fixed; right: 24px; bottom: 24px; z-index: 3; width: min(620px, calc(100% - 28px)); max-height: min(560px, calc(100vh - 48px)); overflow: auto; color: #edf2ff; background: #132038; border: 1px solid #516a93; border-radius: 14px; box-shadow: 0 12px 32px rgb(0 0 0 / 45%); }} .status-term {{ cursor: pointer; border: 0; border-bottom: 1px dashed #8fb5ff; color: #a8c7ff; background: transparent; padding: 0; font: inherit; font-weight: 700; }} .status-term:hover, .status-term:focus {{ color: #d7e6ff; border-bottom-style: solid; }} .status-term-highlight {{ color: #c5d7ff; background: rgb(122 166 255 / 18%); border-radius: 3px; padding: 0 2px; font-weight: 700; }} .status-content {{ margin: 16px 0 0; white-space: pre-wrap; line-height: 1.65; }}
    .empty {{ color: #a9b7cf; margin: 20px 0; }} @media (max-width: 850px) {{ .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .controls input {{ grid-column: span 2; }} }} @media (max-width: 600px) {{ .hero-detail-header {{ flex-wrap: wrap; align-items: flex-start; }} .hero-detail-facts {{ width: 100%; flex-basis: 100%; }} .sort-selects {{ grid-template-columns: 1fr; gap: 6px; }} .sort-selects select, .sort-selects select:first-child, .sort-selects select + select {{ border: 1px solid #394867; border-radius: 9px; }} }}
  </style>
</head>
<body>
  <header><h1>Live A Hero 本地速查</h1><p id="snapshot"></p></header>
  <main>
    <section class="controls" aria-label="筛选条件">
      <input id="query" autofocus placeholder="搜索中文名、日文名、卡片编号或技能内容，例如：阿卡西">
      <label class="filter-control"><span class="control-label">分类</span><select id="kind"><option value="">全角色</option><option value="hero">仅英雄</option><option value="sidekick">仅助手</option></select></label>
      <section class="filter-control multi-select" id="rarity"><span class="control-label" id="rarity-label">稀有度</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="rarity-menu" aria-labelledby="rarity-label">全部</button><div class="multi-select-menu" id="rarity-menu" role="group" aria-labelledby="rarity-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select" id="element"><span class="control-label" id="element-label">属性</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="element-menu" aria-labelledby="element-label">全部</button><div class="multi-select-menu" id="element-menu" role="group" aria-labelledby="element-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select" id="role"><span class="control-label" id="role-label">职能</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="role-menu" aria-labelledby="role-label">全部</button><div class="multi-select-menu" id="role-menu" role="group" aria-labelledby="role-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <label class="filter-control sort-control"><span class="control-label">排序</span><span class="sort-selects"><select id="sortField" aria-label="排序依据"><option value="cardId">卡片 ID</option><option value="name">名称</option><option value="rarity">稀有度</option><option value="hp">HP</option><option value="attack">攻击</option><option value="agility">速度</option></select><select id="sortDirection" aria-label="排序顺序"><option value="asc">升序</option><option value="desc">降序</option></select></span></label>
      <button id="tagSettings" type="button">标签设置</button>
    </section>
    <p class="summary" id="summary"></p><div class="groups" id="groups"></div>
  </main>
  <dialog id="detail"><div class="detail"><div id="detailContent"></div><section id="statusDetail" class="status-detail" hidden aria-labelledby="statusTitle"><div class="detail"><button class="close status-close" aria-label="关闭词条说明">×</button><h2 id="statusTitle"></h2><div class="status-content" id="statusContent"></div></div></section></div></dialog>
  <dialog id="tagSettingsDetail" aria-labelledby="tagSettingsTitle"><div class="detail"><button class="close tag-settings-close" aria-label="关闭标签设置">×</button><h2 id="tagSettingsTitle">标签设置</h2><p class="status-content">英雄卡固定展示属性、职能和类型；助手卡仅展示类型。自定义标签即将开放。</p></div></dialog>
  <script>
    const catalog = {embedded_catalog};
    const avatarUrlPrefix = {json.dumps(avatar_url_prefix)};
    const cards = catalog.cards;
    const byId = new Map(cards.map(card => [card.key, card]));
    const statusById = new Map(catalog.statusTerms.map(term => [term.id, term]));
    const statusTermsByName = new Map();
    for (const term of catalog.statusTerms) {{
      const sameName = statusTermsByName.get(term.name) || [];
      sameName.push(term); statusTermsByName.set(term.name, sameName);
    }}
    const glossaryCandidates = [...statusTermsByName].map(([name, terms]) => ({{name, terms}}));
    const $ = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    const kindLabel = kind => kind === 'hero' ? '英雄' : '助手';
    const displayRarity = card => card.kind === 'hero' ? card.initialRarity : card.rarity;
    function avatarMarkup(card, size) {{
      const avatar = card.avatar || {{status: 'missing', code: null}};
      const label = avatar.status === 'available' ? `${{card.name}} 头像` : `${{card.name}}（本地暂无头像）`;
      if (avatar.status !== 'available' || !avatar.code) return `<span class="avatar ${{size}} avatar-missing" role="img" aria-label="${{escape(label)}}" title="本地暂无头像">?</span>`;
      const filename = avatar.filename || `${{avatar.code}}.png`;
      const source = `${{avatarUrlPrefix}}/${{encodeURIComponent(filename)}}`;
      return `<span class="avatar ${{size}}"><img class="avatar-image" loading="lazy" src="${{escape(source)}}" alt="${{escape(label)}}"></span>`;
    }}
    function useAvatarPlaceholder(image) {{
      const avatar = image.closest('.avatar'); if (!avatar) return;
      avatar.classList.add('avatar-missing'); avatar.textContent = '?'; avatar.title = '本地暂无头像'; avatar.setAttribute('aria-label', '本地暂无头像');
    }}
    function termMarkup(text, candidates) {{
      const terms = [...candidates].sort((left, right) => right.name.length - left.name.length);
      const seenNames = new Set();
      let markup = ''; let textStart = 0; let index = 0;
      while (index < text.length) {{
        const candidate = terms.find(item => text.startsWith(item.name, index));
        if (!candidate) {{ index += 1; continue; }}
        const matchedTerms = candidate.terms || [candidate];
        const status = matchedTerms[0];
        markup += escape(text.slice(textStart, index));
        if (matchedTerms.length === 1 && !seenNames.has(candidate.name)) {{
          markup += `<button class="status-term" type="button" data-status-id="${{escape(status.id)}}">${{escape(candidate.name)}}</button>`;
        }} else {{
          markup += `<span class="status-term-highlight">${{escape(candidate.name)}}</span>`;
        }}
        seenNames.add(candidate.name);
        index += candidate.name.length; textStart = index;
      }}
      return markup + escape(text.slice(textStart));
    }}
    function descriptionMarkup(skill) {{
      return termMarkup(skill.description, skill.statusTerms || []);
    }}
    function statusDescriptionMarkup(status) {{
      return termMarkup(status.description, glossaryCandidates.filter(candidate => candidate.name !== status.name));
    }}
    function showStatusDetail(status) {{
      if (!status) return;
      $('statusTitle').textContent = status.name;
      $('statusContent').innerHTML = statusDescriptionMarkup(status);
      $('statusDetail').hidden = false;
    }}
    function selectedValues(id) {{
      return new Set([...$(id).querySelectorAll('input:checked')].map(input => input.value));
    }}
    function updateMultiSelectLabel(control) {{
      const values = [...selectedValues(control.id)];
      control.querySelector('.multi-select-trigger').textContent = values.length === 0 ? '全部' : values.length === 1 ? values[0] : `已选 ${{values.length}} 项`;
    }}
    function closeMultiSelect(control) {{
      const menu = control.querySelector('.multi-select-menu');
      menu.hidden = true; control.querySelector('.multi-select-trigger').setAttribute('aria-expanded', 'false');
    }}
    function setupMultiSelect(id, values) {{
      const control = $(id); const options = control.querySelector('.multi-select-options');
      for (const value of [...values].filter(Boolean).sort((a,b) => String(a).localeCompare(String(b), 'zh-CN'))) {{
        const label = document.createElement('label'); label.className = 'multi-select-option';
        const input = document.createElement('input'); input.type = 'checkbox'; input.value = value;
        input.addEventListener('change', () => {{ updateMultiSelectLabel(control); render(); }});
        label.append(input, document.createTextNode(value)); options.append(label);
      }}
      control.querySelector('.multi-select-clear').addEventListener('click', () => {{
        for (const input of control.querySelectorAll('input:checked')) input.checked = false;
        updateMultiSelectLabel(control); render();
      }});
    }}
    setupMultiSelect('rarity', new Set(cards.map(card => '★'.repeat(displayRarity(card)))));
    const heroes = cards.filter(card => card.kind === 'hero');
    setupMultiSelect('element', new Set(heroes.map(card => card.element?.label)));
    setupMultiSelect('role', new Set(heroes.map(card => card.role?.label)));
    $('snapshot').textContent = `快照：${{catalog.metadata.snapshotId}} · 英雄 ${{catalog.metadata.heroCardCount}} 张（仅 60 级属性）· 助手 ${{catalog.metadata.sidekickCardCount}} 张（最高技能阶段）· 技能强化 ${{catalog.metadata.skillUpgradeCount}} 项`;
    function matches(card) {{
      const query = $('query').value.trim().toLocaleLowerCase();
      const haystack = [card.name, card.originalName, card.cardId, ...card.aliases, ...card.skills.flatMap(skill => [skill.name, skill.originalName, skill.description])].join('\\n').toLocaleLowerCase();
      const rarity = selectedValues('rarity'); const element = selectedValues('element'); const role = selectedValues('role');
      return (!query || haystack.includes(query)) && (!$('kind').value || card.kind === $('kind').value) && (!rarity.size || rarity.has('★'.repeat(displayRarity(card)))) && (!element.size || element.has(card.element?.label)) && (!role.size || role.has(card.role?.label));
    }}
    function sortValue(card, field) {{
      if (field === 'name') return card.name;
      if (field === 'cardId') return Number(card[field]);
      if (field === 'rarity') return displayRarity(card);
      const stats = card.kind === 'hero' ? card.stats.level60 : card.stats.max;
      return stats?.[field];
    }}
    function compareCards(left, right) {{
      const field = $('sortField').value;
      const direction = $('sortDirection').value === 'asc' ? 1 : -1;
      const leftValue = sortValue(left, field);
      const rightValue = sortValue(right, field);
      if (leftValue == null && rightValue != null) return 1;
      if (leftValue != null && rightValue == null) return -1;
      if (leftValue != null && rightValue != null) {{
        const numericFields = new Set(['cardId', 'rarity', 'hp', 'attack', 'agility']);
        const comparison = numericFields.has(field)
          ? leftValue - rightValue
          : String(leftValue).localeCompare(String(rightValue), 'zh-CN');
        if (comparison) return comparison * direction;
      }}
      return Number(left.cardId) - Number(right.cardId);
    }}
    function render() {{
      const result = cards.filter(matches); const groups = $('groups'); groups.replaceChildren();
      $('summary').textContent = `找到 ${{result.length}} 张卡；输入角色名会按英雄和助手分组。`;
      for (const kind of ['hero', 'sidekick']) {{
        const list = result.filter(card => card.kind === kind).sort(compareCards); if (!list.length) continue;
        const section = document.createElement('section'); const heading = document.createElement('h2'); heading.textContent = `${{kindLabel(kind)}}（${{list.length}}）`; section.append(heading);
        const grid = document.createElement('div'); grid.className = 'results';
        for (const card of list) {{ const button = document.createElement('button'); button.className='card'; button.dataset.key=card.key; const tags = card.kind === 'hero' ? [card.element?.label, card.role?.label, kindLabel(card.kind)] : [kindLabel(card.kind)]; button.innerHTML = `<div class="card-layout">${{avatarMarkup(card, 'avatar-small')}}<div><div class="card-title"><span>${{escape(card.name)}}</span><span>${{escape('★'.repeat(displayRarity(card)))}}</span></div><div class="muted">${{escape(card.originalName)}} · #${{escape(card.cardId)}}</div><div class="tags">${{tags.map(tag => `<span class="tag">${{escape(tag)}}</span>`).join('')}}</div></div></div>`; grid.append(button); }}
        section.append(grid); groups.append(section);
      }}
      if (!result.length) groups.innerHTML = '<p class="empty">没有匹配项。可尝试角色日文名、卡片编号或技能文字。</p>';
    }}
    function showDetail(card) {{
      $('detail').classList.toggle('hero-detail', card.kind === 'hero');
      const stats = card.kind === 'hero'
        ? [['60级 HP',card.stats.level60.hp], ['60级 攻击',card.stats.level60.attack], ['60级 速度',card.stats.level60.agility]]
        : [['稀有度','★'.repeat(card.rarity)], ['1级 HP',card.stats.level1.hp], ['1级 攻击',card.stats.level1.attack], ['1级 速度',card.stats.level1.agility], ['最高阶段 HP',card.stats.max.hp], ['最高阶段 攻击',card.stats.max.attack], ['最高阶段 速度',card.stats.max.agility]];
      const detailClose = '<button class="close detail-close" aria-label="关闭">×</button>';
      const heading = `<div class="detail-heading">${{avatarMarkup(card, 'avatar-large')}}<div><h2>${{escape(kindLabel(card.kind))}} · ${{escape(card.name)}}</h2><p class="muted">${{escape(card.originalName)}} · 卡片编号 #${{escape(card.cardId)}}${{card.kind === 'sidekick' ? ` · 最高技能阶段 ${{escape(card.skillLevel)}}` : ''}}</p></div></div>`;
      const heroHeader = card.kind === 'hero'
        ? `<div class="hero-detail-header">${{detailClose}}${{heading}}<div class="hero-detail-facts"><div class="hero-detail-fact"><div class="muted">属性</div><strong>${{escape(card.element?.label || '不适用')}}</strong></div><div class="hero-detail-fact"><div class="muted">职能</div><strong>${{escape(card.role?.label || '不适用')}}</strong></div></div></div>`
        : `${{detailClose}}${{heading}}`;
      const upgradeHtml = card.skillUpgrades.length ? `<h3>技能强化（独立记录）</h3>${{card.skillUpgrades.map(upgrade => `<article class="skill upgrade"><strong>${{escape(upgrade.before.name)}} → ${{escape(upgrade.after.name)}}</strong><div class="muted">技能 #${{escape(upgrade.before.skillId)}} → #${{escape(upgrade.after.skillId)}}${{upgrade.questId ? ` · 任务 #${{escape(upgrade.questId)}}` : ''}}</div><div><b>强化前：</b>${{descriptionMarkup(upgrade.before)}}</div><div><b>强化后（最高等级）：</b>${{descriptionMarkup(upgrade.after)}}</div>${{upgrade.after.descriptionSource === '日文原文' ? '<div class="source">日文原文（官方简中未覆盖）</div>' : ''}}</article>`).join('')}}` : '';
      $('detailContent').innerHTML = `${{heroHeader}}<div class="stat-grid">${{stats.map(([label,value]) => `<div class="stat"><div class="muted">${{label}}</div><strong>${{escape(value ?? '—')}}</strong></div>`).join('')}}</div><h3>关联技能</h3>${{card.skills.map(skill => `<article class="skill"><strong>${{escape(skill.relation)}} · ${{escape(skill.name)}}</strong><div class="muted">${{escape(skill.originalName)}} · #${{escape(skill.skillId)}}</div><div>${{descriptionMarkup(skill)}}</div>${{skill.nameSource === '日文原文' || skill.descriptionSource === '日文原文' ? '<div class="source">日文原文（官方简中未覆盖）</div>' : ''}}</article>`).join('')}}${{upgradeHtml}}`;
      $('detail').showModal();
    }}
    $('query').addEventListener('input', render);
    for (const id of ['kind', 'sortField', 'sortDirection']) $(id).addEventListener('change', render);
    document.addEventListener('click', event => {{
      const trigger = event.target.closest('button.multi-select-trigger');
      if (trigger) {{
        const control = trigger.closest('.multi-select'); const menu = control.querySelector('.multi-select-menu');
        for (const other of document.querySelectorAll('.multi-select')) if (other !== control) closeMultiSelect(other);
        menu.hidden = !menu.hidden; trigger.setAttribute('aria-expanded', String(!menu.hidden)); return;
      }}
      if (!event.target.closest('.multi-select')) for (const control of document.querySelectorAll('.multi-select')) closeMultiSelect(control);
      const closeButton = event.target.closest('button.detail-close'); if (closeButton) {{ $('detail').close(); return; }}
      const statusButton = event.target.closest('button.status-term'); if (statusButton) {{ showStatusDetail(statusById.get(statusButton.dataset.statusId)); return; }}
      const button = event.target.closest('button.card'); if (button) showDetail(byId.get(button.dataset.key));
    }});
    document.addEventListener('keydown', event => {{
      if (event.key !== 'Escape') return;
      const openControl = [...document.querySelectorAll('.multi-select')].find(control => !control.querySelector('.multi-select-menu').hidden);
      if (openControl) {{ event.preventDefault(); closeMultiSelect(openControl); return; }}
      if (!$('statusDetail').hidden) {{ event.preventDefault(); $('statusDetail').hidden = true; }}
    }});
    document.addEventListener('error', event => {{ if (event.target.matches('img.avatar-image')) useAvatarPlaceholder(event.target); }}, true);
    document.querySelector('.status-close').addEventListener('click', () => $('statusDetail').hidden = true);
    $('detail').addEventListener('close', () => $('statusDetail').hidden = true);
    $('tagSettings').addEventListener('click', () => $('tagSettingsDetail').showModal());
    document.querySelector('.tag-settings-close').addEventListener('click', () => $('tagSettingsDetail').close());
    render();
  </script>
</body>
</html>"""


def _build_cards(
    raw_cards: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    aliases: dict[str, list[str]],
    avatars: dict[str, dict[str, dict[str, str | None]]],
    status_terms: dict[str, dict[str, str]],
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
        append_ids = raw_card.get("equipmentAppendSkills") or [] if kind == "sidekick" else []
        card_skills = [
            *[_skill_row(skill_id, "主动技能" if kind == "hero" else "主动技能（最高阶段）", skills, localized, status_terms) for skill_id in active_ids],
            *[_skill_row(skill_id, "装备技能（最高等级）", skills, localized, status_terms) for skill_id in _highest_skill_ids(equipment_ids)],
            *[_skill_row(skill_id, "追加装备技能（最高等级）", skills, localized, status_terms) for skill_id in _highest_skill_ids(append_ids)],
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
                "avatar": _avatar_for_card(resource_name, original_name, name, avatars),
                "rarity": raw_card.get("rarity", 0),
                "initialRarity": raw_card.get("initialRarity") if kind == "hero" else None,
                "element": _element(raw_card.get("element")) if kind == "hero" else None,
                "role": _role(raw_card.get("role")) if kind == "hero" else None,
                "stats": _stats(raw_card.get("growths") or [], kind),
                "skills": card_skills,
                "skillLevel": raw_card.get("levelZone") if kind == "sidekick" else None,
                "skillUpgrades": _skill_upgrades(raw_card, skills, localized, status_terms) if kind == "hero" else [],
            }
        )
    return result


def _skill_row(
    skill_id: int | str,
    relation: str,
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
    description_override: str | None = None,
    description_source_override: str | None = None,
    effects_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_skill = skills.get(str(skill_id))
    if raw_skill is None:
        raise ValueError(f"card references missing skill: {skill_id}")
    original_name = raw_skill.get("skillName") or str(skill_id)
    original_description = _clean_text(raw_skill.get("description", ""))
    name = localized.get(f"SKILL_NAME_{skill_id}") or original_name
    description = description_override or localized.get(f"SKILL_DESCRIPTION_{skill_id}") or original_description
    cleaned_description = _clean_text(description)
    description_source = description_source_override or (
        "官方简中" if localized.get(f"SKILL_DESCRIPTION_{skill_id}") else "日文原文"
    )
    skill_for_status_terms = (
        {**raw_skill, "effects": effects_override}
        if effects_override is not None
        else raw_skill
    )
    return {
        "skillId": str(skill_id),
        "relation": relation,
        "name": name,
        "nameSource": "官方简中" if localized.get(f"SKILL_NAME_{skill_id}") else "日文原文",
        "originalName": original_name,
        "description": cleaned_description,
        "descriptionSource": description_source,
        "statusTerms": _status_terms_for_skill(skill_for_status_terms, cleaned_description, status_terms),
    }


def _unique_skills(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {}
    for card in cards:
        for skill in card["skills"]:
            indexed.setdefault(skill["skillId"], skill)
    return sorted(indexed.values(), key=lambda skill: (skill["name"], skill["skillId"]))


def _unique_skill_upgrades(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for card in cards:
        for upgrade in card["skillUpgrades"]:
            rows.append(
                {
                    "cardKey": card["key"],
                    "cardId": card["cardId"],
                    "cardName": card["name"],
                    "cardOriginalName": card["originalName"],
                    **upgrade,
                }
            )
    return sorted(rows, key=lambda row: (row["cardName"], row["cardId"], row["before"]["skillId"]))


def _avatar_index(
    char_map: dict[str, dict[str, Any]],
    icon_dir: Path,
    avatar_overrides_path: Path | None = None,
) -> dict[str, dict[str, dict[str, str | None]]]:
    candidates: dict[str, dict[str, list[str]]] = {"jp": {}, "cn": {}}
    index: dict[str, dict[str, dict[str, str | None]]] = {"code": {}, "jp": {}, "cn": {}}
    for code, entry in char_map.items():
        index["code"][code.lower()] = {
            "status": "available" if (icon_dir / f"{code}.png").is_file() else "missing",
            "code": code,
        }
        for field in candidates:
            name = _canonical_character_name(entry.get(field))
            if name:
                candidates[field].setdefault(name, []).append(code)

    for field, names in candidates.items():
        for name, codes in names.items():
            if len(codes) != 1:
                continue
            code = codes[0]
            index[field][name] = {
                "status": "available" if (icon_dir / f"{code}.png").is_file() else "missing",
                "code": code,
            }

    if avatar_overrides_path and avatar_overrides_path.is_file():
        for resource_name, filename in _read_json(avatar_overrides_path).items():
            if not isinstance(filename, str) or Path(filename).name != filename:
                continue
            index["code"][resource_name.lower()] = {
                "status": "available" if (icon_dir / filename).is_file() else "missing",
                "code": resource_name,
                "filename": filename,
            }
    return index


def _avatar_for_card(
    resource_name: str,
    original_name: str,
    localized_name: str,
    avatars: dict[str, dict[str, dict[str, str | None]]],
) -> dict[str, str | None]:
    avatar = avatars["code"].get(resource_name.lower()) or avatars["jp"].get(
        _canonical_character_name(original_name)
    ) or avatars["cn"].get(
        _canonical_character_name(localized_name)
    )
    return dict(avatar) if avatar else {"status": "missing", "code": None}


def _canonical_character_name(name: str | None) -> str:
    """Apply the same decorative-symbol cleanup used by the character map builder."""
    return re.sub(r"[⇌↔←→⇔\u2000-\u206f]", "", name or "").strip()


def _highest_sidekick_cards(raw_cards: dict[str, Any]) -> list[dict[str, Any]]:
    entries = raw_cards.values() if isinstance(raw_cards, dict) else raw_cards
    selected: dict[str, dict[str, Any]] = {}
    for card in entries:
        key = str(card.get("stockId", card.get("sidekickCardId")))
        if key not in selected or card.get("levelZone", 0) > selected[key].get("levelZone", 0):
            selected[key] = card
    return list(selected.values())


def _highest_hero_cards(raw_cards: dict[str, Any]) -> list[dict[str, Any]]:
    """Collapse star-upgrade variants by their original in-game name."""
    entries = raw_cards.values() if isinstance(raw_cards, dict) else raw_cards
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in entries:
        key = card.get("cardName") or str(card.get("heroCardId"))
        grouped.setdefault(key, []).append(card)

    selected = []
    for variants in grouped.values():
        highest = max(variants, key=lambda card: card.get("rarity", 0))
        merged = dict(highest)
        merged["initialRarity"] = min(card.get("rarity", 0) for card in variants)
        seen_changes = set()
        merged_quests = []
        for variant in variants:
            for quest in variant.get("skillUpgradeQuestInfos") or []:
                for change in quest.get("changeSkills") or []:
                    signature = (
                        quest.get("questId"),
                        quest.get("skillUpgrade"),
                        change.get("beforeSkillId"),
                        change.get("afterSkillId"),
                    )
                    if signature in seen_changes:
                        continue
                    seen_changes.add(signature)
                    merged_quests.append(
                        {
                            "questId": quest.get("questId"),
                            "skillUpgrade": quest.get("skillUpgrade"),
                            "changeSkills": [change],
                        }
                    )
        merged["skillUpgradeQuestInfos"] = merged_quests
        selected.append(merged)
    return selected


def _highest_skill_ids(skill_ids: list[int | str]) -> list[int | str]:
    return [skill_ids[-1]] if skill_ids else []


def _skill_upgrades(
    raw_card: dict[str, Any],
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    learn_no_by_skill = {
        str(item["skillId"]): item.get("skillLearnNo")
        for item in raw_card.get("skillProvider", {}).get("activeSkills", [])
    }
    upgrades = []
    for quest in raw_card.get("skillUpgradeQuestInfos") or []:
        for change in quest.get("changeSkills") or []:
            before_id = change.get("beforeSkillId")
            after_id = change.get("afterSkillId")
            if before_id is None or after_id is None:
                continue
            learn_no = learn_no_by_skill.get(str(before_id))
            upgrades.append(
                {
                    "skillLevel": quest.get("skillUpgrade"),
                    "questId": str(quest["questId"]) if quest.get("questId") is not None else None,
                    "before": _skill_row(before_id, f"技能 {learn_no}" if learn_no else "强化前", skills, localized, status_terms),
                    "after": _highest_upgrade_skill_row(after_id, skills, localized, status_terms),
                }
            )
    return upgrades


def _highest_upgrade_skill_row(
    skill_id: int | str,
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
) -> dict[str, Any]:
    raw_skill = skills.get(str(skill_id))
    if raw_skill is None:
        raise ValueError(f"card references missing skill: {skill_id}")

    condition_groups: dict[int, list[dict[str, Any]]] = {}
    base_effects = []
    for effect in raw_skill.get("effects") or []:
        if _clean_text(effect.get("conditionDescription", "")):
            condition_groups.setdefault(effect.get("conditionGroupId", 0), []).append(effect)
        else:
            base_effects.append(effect)
    if not condition_groups:
        return _skill_row(skill_id, "强化后", skills, localized, status_terms)

    highest_effects = [
        max(effects, key=lambda effect: (effect.get("conditionPriority", 0), effect.get("serialNo", 0)))
        for effects in condition_groups.values()
    ]
    highest_effects.sort(key=lambda effect: effect.get("serialNo", 0))
    final_description = "\n".join(
        part
        for part in [
            _clean_text(raw_skill.get("description", "")),
            *(_clean_text(effect.get("conditionDescription", "")) for effect in highest_effects),
        ]
        if part
    )
    return _skill_row(
        skill_id,
        "强化后",
        skills,
        localized,
        status_terms,
        description_override=final_description,
        description_source_override="日文原文",
        effects_override=[*base_effects, *highest_effects],
    )


def _aliases_by_original(aliases: dict[str, str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for alias, original_name in aliases.items():
        result.setdefault(original_name, []).append(alias)
    return {key: sorted(values) for key, values in result.items()}


def _element(value: int | None) -> dict[str, Any]:
    return {"code": value, "label": ELEMENT_LABELS.get(value, f"属性代码 {value}")}


def _role(value: int | None) -> dict[str, Any]:
    return {"code": value, "label": ROLE_LABELS.get(value, f"定位代码 {value}")}


def _stats(growths: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    if kind == "hero":
        level60 = next((growth for growth in growths if growth.get("level") == 60), None)
        return {"level60": _stat_values(level60) if level60 else {}}
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


def _status_terms_by_id(localized: dict[str, str]) -> dict[str, dict[str, dict[str, str]]]:
    result = {"effect": {}, "skill": {}}
    for source, prefix in (("effect", "OVERRIDE_STATUS_NAME_"), ("skill", "STATUS_NAME_")):
        for key, name in localized.items():
            if not key.startswith(prefix) or not name:
                continue
            status_id = key.removeprefix(prefix)
            description = localized.get(f"{prefix.replace('_NAME_', '_DESCRIPTION_')}{status_id}", "")
            if not description:
                continue
            result[source][status_id] = {
                "id": status_id,
                "name": name,
                "description": _clean_status_description(description),
            }
    result["all"] = {**result["effect"], **result["skill"]}
    return result


def _status_terms_for_skill(
    raw_skill: dict[str, Any], description: str, status_terms: dict[str, dict[str, dict[str, str]]]
) -> list[dict[str, str]]:
    candidates: dict[str, dict[str, dict[str, str]]] = {}
    for effect in raw_skill.get("effects") or []:
        status_term = status_terms["effect"].get(str(effect.get("skillEffectId")))
        if status_term and status_term["name"] in description:
            candidates.setdefault(status_term["name"], {})[status_term["id"]] = status_term
    skill_status = status_terms["skill"].get(str(raw_skill.get("skillId")))
    if skill_status and skill_status["name"] in description:
        candidates.setdefault(skill_status["name"], {})[skill_status["id"]] = skill_status
    return [next(iter(terms.values())) for terms in candidates.values() if len(terms) == 1]


def _clean_status_description(text: str) -> str:
    return _clean_text(re.sub(r"<br\s*/?>", "\n", text or "", flags=re.IGNORECASE))


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
