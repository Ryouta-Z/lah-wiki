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

try:
    from scripts.assistant_tags import (
        DEFAULT_ASSISTANT_TAGS_PATH,
        read_assistant_tag_config,
        tags_for_assignments,
        validate_assistant_tag_config,
    )
    from scripts.hero_tags import (
        DEFAULT_HERO_TAGS_PATH,
        read_hero_tag_config,
        tags_for_assignments as hero_tags_for_assignments,
        validate_hero_tag_config,
    )
except ModuleNotFoundError:  # Allow `python scripts/lah_quickref.py` from the project root.
    from assistant_tags import (  # type: ignore[no-redef]
        DEFAULT_ASSISTANT_TAGS_PATH,
        read_assistant_tag_config,
        tags_for_assignments,
        validate_assistant_tag_config,
    )
    from hero_tags import (  # type: ignore[no-redef]
        DEFAULT_HERO_TAGS_PATH,
        read_hero_tag_config,
        tags_for_assignments as hero_tags_for_assignments,
        validate_hero_tag_config,
    )

ROOT = Path(__file__).parent.parent
DEFAULT_SNAPSHOT_DIR = ROOT / "data" / "cache" / "lah-localization"
DEFAULT_CATALOG_PATH = ROOT / "data" / "quickref_catalog.json"
DEFAULT_SITE_PATH = ROOT / "quickref" / "index.html"
DEFAULT_ALIASES_PATH = ROOT / "data" / "aliases.json"
DEFAULT_CHAR_MAP_PATH = ROOT / "data" / "char_map.json"
DEFAULT_ICON_DIR = ROOT / "data" / "images" / "icon"
DEFAULT_AVATAR_OVERRIDES_PATH = ROOT / "data" / "quickref_avatar_overrides.json"
DEFAULT_SIDEKICK_AVATAR_OVERRIDES_PATH = (
    ROOT / "data" / "quickref_sidekick_avatar_overrides.json"
)
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

# These terms are either tied to a particular skill or need a more useful
# explanation than the generic status record carries.  They remain ordinary
# status-term records in the catalog, so the existing clickable glossary still
# works; inlineDescription is shown only on the first occurrence in a skill.
SPECIAL_STATUS_TERMS_BY_SKILL: dict[str, list[dict[str, str]]] = {
    "1025205": [{
        "id": "special:steel-fist",
        "name": "钢拳",
        "description": "每个钢拳使该技能伤害+10%；自身获得DEF上升时钢拳+1，最多3个。",
        "inlineDescription": "每个钢拳使伤害+10%；自身获得DEF上升时钢拳+1，最多3个",
        "source": "专用说明",
    }],
    "1033106": [{
        "id": "special:sunlight",
        "name": "阳光",
        "description": "ATK+20%。",
        "inlineDescription": "ATK+20%",
        "source": "官方简中",
    }],
    "1033107": [{
        "id": "special:new-green",
        "name": "新绿",
        "description": "绝境状态时解除，并依附加者基础ATK的50%恢复HP。",
        "inlineDescription": "绝境时解除，并依附加者基础ATK的50%恢复HP",
        "source": "官方简中",
    }],
    "1034105": [{
        "id": "special:continuous-jump",
        "name": "连续跳跃",
        "description": "每个蓄能数SPD+1；自身获得SPD上升时蓄能数+1，最多50。",
        "inlineDescription": "每个蓄能数SPD+1；自身获得SPD上升时蓄能数+1，最多50",
        "source": "官方简中",
    }],
    "1082105": [{
        "id": "special:concert",
        "name": "协奏",
        "description": "以获得View的技能取得的View变为1.5倍。",
        "inlineDescription": "以获得View的技能取得的View变为1.5倍",
        "source": "官方简中",
    }],
    "1082106": [{
        "id": "special:concert",
        "name": "协奏",
        "description": "以获得View的技能取得的View变为1.5倍。",
        "inlineDescription": "以获得View的技能取得的View变为1.5倍",
        "source": "官方简中",
    }],
    "1082107": [{
        "id": "special:concert",
        "name": "协奏",
        "description": "以获得View的技能取得的View变为1.5倍。",
        "inlineDescription": "以获得View的技能取得的View变为1.5倍",
        "source": "官方简中",
    }],
    "1112201": [{
        "id": "special:shadow-copy",
        "name": "影印",
        "description": "不可叠加的蓄能状态；由幻想的算哲的技能处理，且我方所有幻想的算哲无法战斗时解除。",
        "inlineDescription": "不可叠加的蓄能状态；我方所有幻想的算哲无法战斗时解除",
        "source": "专用说明",
    }],
    "1112202": [{
        "id": "special:mirror-realm",
        "name": "镜界",
        "matchName": "鏡界",
        "description": "幻想的算哲的专用计量；主动技能附加增益时+1，并按该增益持续回合数额外增加，最多20。",
        "inlineDescription": "专用计量；主动技能附加增益时+1，并按持续回合数额外增加，最多20",
        "source": "专用说明",
    }],
    "1112204": [
        {
            "id": "special:mirror-realm",
            "name": "镜界",
            "matchName": "鏡界",
            "description": "幻想的算哲的专用计量；主动技能附加增益时+1，并按该增益持续回合数额外增加，最多20。",
            "inlineDescription": "专用计量；主动技能附加增益时+1，并按持续回合数额外增加，最多20",
            "source": "专用说明",
        },
        {
            "id": "special:second-arrow",
            "name": "马肖迪克·尼尔",
            "matchName": "マーショディク・ニール",
            "description": "第二箭（暂译）：镜界为5～9时消耗5并造成40%全体伤害；10～14时消耗10并造成60%；15～20时消耗15并造成80%。不获得View或连击数。",
            "inlineDescription": "第二箭（暂译）：依镜界消耗5/10/15，对全体造成40/60/80%伤害；不获得View或连击数",
            "source": "专用说明",
        },
    ],
}

# 幻想的算哲的强化技能与基础技能共用同一组专用计量词条。
SPECIAL_STATUS_TERMS_BY_SKILL["1112205"] = [dict(term) for term in SPECIAL_STATUS_TERMS_BY_SKILL["1112201"]]
SPECIAL_STATUS_TERMS_BY_SKILL["1112206"] = [dict(term) for term in SPECIAL_STATUS_TERMS_BY_SKILL["1112202"]]
SPECIAL_STATUS_TERMS_BY_SKILL["1112207"] = [dict(term) for term in SPECIAL_STATUS_TERMS_BY_SKILL["1112204"]]

# 「解除所有减益效果」 is the terminal form of the earlier three-debuff
# effect.  Retaining both makes the highest rank read as two simultaneous rules.
SUBSUMED_HIGHEST_EFFECT_IDS = {209: {594}}
UPGRADE_CONDITION_TEXT_OVERRIDES = {
    ("1030107", 12): "发动前，解除自身2个减益效果。",
}


def build_catalog(
    snapshot_dir: Path,
    aliases_path: Path = DEFAULT_ALIASES_PATH,
    char_map_path: Path = DEFAULT_CHAR_MAP_PATH,
    icon_dir: Path = DEFAULT_ICON_DIR,
    avatar_overrides_path: Path = DEFAULT_AVATAR_OVERRIDES_PATH,
    sidekick_avatar_overrides_path: Path = DEFAULT_SIDEKICK_AVATAR_OVERRIDES_PATH,
    assistant_tags_path: Path | None = None,
    hero_tags_path: Path | None = None,
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
    sidekick_avatars = _sidekick_avatar_overrides(
        icon_dir, sidekick_avatar_overrides_path
    )
    status_terms = _status_terms_by_id(localized)

    cards = [
        *_build_cards(
            _highest_hero_cards(hero_cards),
            skills,
            localized,
            aliases,
            avatars,
            status_terms,
            "hero",
        ),
        *_build_cards(
            _highest_sidekick_cards(sidekick_cards),
            skills,
            localized,
            aliases,
            avatars,
            status_terms,
            "sidekick",
            sidekick_avatars,
        ),
    ]
    cards.sort(key=lambda card: (card["kind"], card["name"], card["cardId"]))
    assistant_tag_config = None
    if assistant_tags_path is not None:
        assistant_tag_config = read_assistant_tag_config(assistant_tags_path)
        sidekick_keys = {card["key"] for card in cards if card["kind"] == "sidekick"}
        assistant_tag_config = validate_assistant_tag_config(assistant_tag_config, sidekick_keys)
        tags_by_sidekick = tags_for_assignments(assistant_tag_config)
        for card in cards:
            if card["kind"] == "sidekick":
                card["tags"] = tags_by_sidekick.get(card["key"], [])

    hero_tag_config = None
    if hero_tags_path is not None:
        hero_tag_config = read_hero_tag_config(hero_tags_path)
        hero_keys = {card["key"] for card in cards if card["kind"] == "hero"}
        hero_tag_config = validate_hero_tag_config(hero_tag_config, hero_keys)
        tags_by_hero = hero_tags_for_assignments(hero_tag_config)
        for card in cards:
            if card["kind"] == "hero":
                card["tags"] = tags_by_hero.get(card["key"], [])

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
            "translationPolicy": "官方简中优先；缺失片段保留日文原文。",
            "heroStatPolicy": "同名英雄仅保留最高星卡的 60 级属性；无 60 级数据的特殊卡保留技能并标记。",
            "sidekickSkillPolicy": "每名助手仅保留最高阶段的主动技能与最高等级装备技能。",
        },
        "cards": cards,
        "skills": skill_rows,
        "skillUpgrades": skill_upgrades,
        "statusTerms": sorted(status_terms["all"].values(), key=lambda term: (term["name"], term["id"])),
        "assistantTags": assistant_tag_config["tags"] if assistant_tag_config else [],
        "heroTags": hero_tag_config["tags"] if hero_tag_config else [],
    }


def write_catalog(catalog: dict[str, Any], output_path: Path) -> None:
    _write_json_atomic(output_path, catalog)


def write_static_site(
    catalog: dict[str, Any], output_path: Path, icon_dir: Path = DEFAULT_ICON_DIR
) -> None:
    avatar_url_prefix = Path(os.path.relpath(icon_dir, start=output_path.parent)).as_posix()
    official_ui_dir = ROOT / "data" / "cache" / "official-ui-candidates" / "selected"
    local_official_asset_prefix = (
        Path(os.path.relpath(official_ui_dir, start=output_path.parent)).as_posix()
        if official_ui_dir.is_dir()
        else ""
    )
    _write_text_atomic(
        output_path,
        render_static_html(
            catalog,
            avatar_url_prefix,
            local_official_asset_prefix=local_official_asset_prefix,
            use_official_card_layout=True,
        ),
    )


def rebuild_quickref(
    assistant_tags_path: Path = DEFAULT_ASSISTANT_TAGS_PATH,
    hero_tags_path: Path = DEFAULT_HERO_TAGS_PATH,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    site_path: Path = DEFAULT_SITE_PATH,
) -> dict[str, Any]:
    """Rebuild the public offline catalog after a local administrator saves tags."""
    catalog = build_catalog(
        snapshot_dir, assistant_tags_path=assistant_tags_path, hero_tags_path=hero_tags_path
    )
    write_catalog(catalog, catalog_path)
    write_static_site(catalog, site_path)
    return catalog


def render_static_html(
    catalog: dict[str, Any],
    avatar_url_prefix: str = "../data/images/icon",
    *,
    local_official_asset_prefix: str = "",
    use_official_card_layout: bool = False,
    include_tag_settings: bool = True,
) -> str:
    embedded_catalog = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    tag_settings_button = '      <button id="tagSettings" type="button">标签设置</button>' if include_tag_settings else ""
    tag_settings_dialog = """  <dialog id="tagSettingsDetail" aria-labelledby="tagSettingsTitle"><div class="detail"><button class="close tag-settings-close" aria-label="关闭标签设置">×</button><h2 id="tagSettingsTitle">标签管理</h2><p class="status-content">本页仅用于查询。请先在项目根目录运行 <code>uv run python scripts/tag_admin.py</code>，再打开 <a href="http://127.0.0.1:8787/" target="_blank" rel="noreferrer">本机标签管理页</a> 维护英雄和助手归属。保存后会自动更新本页。</p></div></dialog>
""" if include_tag_settings else ""
    tag_settings_listeners = """    $('tagSettings').addEventListener('click', () => $('tagSettingsDetail').showModal());
    document.querySelector('.tag-settings-close').addEventListener('click', () => $('tagSettingsDetail').close());
""" if include_tag_settings else ""
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
    .controls {{ display: grid; grid-template-columns: minmax(220px, 2fr) repeat(5, minmax(105px, 1fr)) minmax(190px, 1.5fr) minmax(110px, 1fr); gap: 10px; align-items: end; }}
    input, select, .controls button {{ width: 100%; border: 1px solid #394867; border-radius: 9px; background: #172235; color: #edf2ff; padding: 10px; font: inherit; font-size: 15px; }} .controls button {{ cursor: pointer; }} .controls button:hover, .controls button:focus {{ border-color: #77a5ff; background: #1b2c49; }}
    .filter-control {{ display: grid; gap: 5px; min-width: 0; }} .control-label {{ color: #b9c7df; font-size: 13px; font-weight: 700; }} .sort-selects {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(82px, auto); }} .sort-selects select {{ border-radius: 0; }} .sort-selects select:first-child {{ border-radius: 9px 0 0 9px; }} .sort-selects select + select {{ border-left: 0; border-radius: 0 9px 9px 0; }} .multi-select {{ position: relative; }} .multi-select-trigger {{ display: flex; justify-content: space-between; align-items: center; min-width: 0; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }} .multi-select-trigger::after {{ content: '▾'; flex: 0 0 auto; margin-left: 6px; color: #b9c7df; }} .multi-select-menu {{ position: absolute; z-index: 4; top: calc(100% + 6px); left: 0; width: max-content; min-width: 100%; max-width: min(310px, calc(100vw - 32px)); padding: 8px; border: 1px solid #516a93; border-radius: 9px; background: #132038; box-shadow: 0 12px 32px rgb(0 0 0 / 35%); }} .multi-select-options {{ display: grid; gap: 2px; max-height: 260px; overflow: auto; }} .multi-select-option {{ display: flex; align-items: center; gap: 8px; padding: 7px; border-radius: 6px; cursor: pointer; }} .multi-select-option:hover {{ background: #1b2c49; }} .multi-select-option input {{ width: auto; margin: 0; padding: 0; border: 0; background: transparent; accent-color: #77a5ff; }} .multi-select-clear {{ margin-top: 8px; border-color: #516a93 !important; background: #1c2b46 !important; }} .tag-select .multi-select-options {{ max-height: none; overflow: visible; }} .tag-menu-level {{ position: relative; display: grid; gap: 2px; min-width: 180px; }} .tag-menu-level .tag-menu-level {{ position: absolute; z-index: 1; top: -8px; left: calc(100% + 14px); max-height: 260px; padding: 8px; overflow: auto; border: 1px solid #516a93; border-radius: 9px; background: #132038; box-shadow: 0 12px 32px rgb(0 0 0 / 35%); }} .tag-menu-branch {{ border: 0 !important; background: transparent !important; text-align: left; padding: 7px !important; }} .tag-menu-branch::after {{ content: '›'; float: right; margin-left: 20px; color: #b9c7df; }} .tag-menu-branch.is-active {{ background: #1b2c49 !important; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0; color: #b9c7df; }} .pill {{ padding: 6px 10px; border-radius: 999px; background: #1f2c43; }}
    .groups {{ display: grid; gap: 28px; }} h2 {{ margin: 0 0 10px; font-size: 22px; }} .results {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }}
    button.card {{ cursor: pointer; min-width: 0; text-align: left; border: 1px solid #31425f; border-radius: 12px; color: inherit; padding: 15px; background: #162238; font: inherit; }} button.card:hover, button.card:focus {{ border-color: #77a5ff; background: #1b2c49; }} .card-layout {{ display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 12px; align-items: center; }}
    .card-title {{ display: flex; justify-content: space-between; gap: 8px; font-weight: 700; }} .muted {{ color: #a9b7cf; font-size: 13px; }} .tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }} .tag {{ background: #293b59; border-radius: 5px; padding: 3px 7px; font-size: 12px; }}
    .avatar {{ display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #4d6a98; border-radius: 50%; background: #263c60; color: #d8e7ff; font-weight: 700; }} .avatar img {{ width: 100%; height: 100%; object-fit: cover; }} .avatar-small {{ width: 58px; height: 58px; font-size: 24px; }} .avatar-large {{ width: 86px; height: 86px; font-size: 34px; }} .avatar-missing {{ border-style: dashed; color: #b7c8e5; }}
    body.official-card-layout .results {{ grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }} body.official-card-layout button.card {{ min-height: 150px; padding: 14px; border-color: rgb(212 223 255 / 19%); border-radius: 16px; background: rgb(7 13 30 / 69%); box-shadow: inset 0 1px rgb(255 255 255 / 7%); }} body.official-card-layout .card-layout {{ grid-template-columns: 104px minmax(0, 1fr); gap: 12px; align-items: start; }} body.official-card-layout .portrait-block {{ position: relative; min-height: 126px; }} body.official-card-layout .portrait-shell {{ position: relative; width: 100px; height: 100px; }} body.official-card-layout .official-frame {{ position: absolute; inset: 0; z-index: 1; width: 100%; height: 100%; pointer-events: none; }} body.official-card-layout .official-frame-fallback {{ border: 2px solid #7d879b; border-radius: 8px; opacity: .8; }} body.official-card-layout .role-badge {{ position: absolute; z-index: 2; left: 0; bottom: 0; display: inline-flex; align-items: center; gap: 4px; min-height: 22px; padding: 2px 3px; }} body.official-card-layout .role-badge.sidekick {{ left: 50%; transform: translateX(-50%); }} body.official-card-layout .role-badge .role-icon {{ width: 18px; height: 18px; }} body.official-card-layout .role-badge .role-wordmark {{ width: auto; height: 16px; }} body.official-card-layout .role-badge.sidekick .role-wordmark {{ height: 14px; }} body.official-card-layout .role-fallback {{ padding: 3px 7px; border-radius: 999px; background: #233658; color: #dce7ff; font-size: 11px; font-weight: 800; letter-spacing: .08em; }} body.official-card-layout .card-avatar {{ position: absolute; inset: 7px; width: auto; height: auto; border-radius: 0; transition: transform 300ms cubic-bezier(0.23, 1, 0.32, 1); }} body.official-card-layout button.card:is(:hover, :focus-visible) .card-avatar {{ transform: scale(1.10); }} body.official-card-layout .card-avatar img {{ object-fit: cover; }} body.official-card-layout .card-copy {{ display: flex; min-width: 0; flex-direction: column; align-items: stretch; }} body.official-card-layout .name-copy {{ min-width: 0; }} body.official-card-layout .card-name {{ margin: 0; font-size: 20px; line-height: 1.12; letter-spacing: -.04em; text-wrap: balance; }} body.official-card-layout .card-jp-name {{ margin: 4px 0 0; color: #aeb9d5; font-size: 11px; line-height: 1.3; text-wrap: pretty; }} body.official-card-layout .attribute-stack {{ display: flex; flex-direction: column; align-items: center; gap: 5px; margin: 9px auto 0; }} body.official-card-layout .hero-element {{ display: inline-flex; width: 28px; height: 28px; align-items: center; justify-content: center; overflow: hidden; border-radius: 7px; box-shadow: 0 0 0 1px rgb(255 255 255 / 15%), 0 5px 10px rgb(0 0 0 / 20%); }} body.official-card-layout .hero-element img {{ display: block; width: 100%; height: 100%; object-fit: contain; }} body.official-card-layout .hero-role {{ display: inline-flex; align-items: center; min-height: 24px; padding: 4px 8px; border: 1px solid rgb(173 246 255 / 68%); border-radius: 8px; color: #061524; background: linear-gradient(135deg, #b9f7ff, #2cb8e8); box-shadow: 0 4px 10px rgb(25 202 239 / 22%), inset 0 1px rgb(255 255 255 / 62%); font-size: 12px; font-weight: 900; line-height: 1.1; white-space: nowrap; }} body.official-card-layout .card-tags {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px; margin-top: 10px; }} body.official-card-layout .card-tags .tag {{ min-width: 0; overflow: hidden; padding: 4px 5px; font-size: 11px; line-height: 1.2; text-align: center; text-overflow: ellipsis; white-space: nowrap; }} @media (prefers-reduced-motion: reduce) {{ body.official-card-layout .card-avatar {{ transition: none; }} body.official-card-layout button.card:is(:hover, :focus-visible) .card-avatar {{ transform: none; }} }}
    body.official-card-layout .hero-metadata {{ display: grid; grid-template-columns: max-content minmax(0, 1fr); align-items: stretch; gap: 10px; margin-top: 9px; }} body.official-card-layout .hero-metadata .attribute-stack {{ height: 82px; justify-content: space-between; margin: 0; }} body.official-card-layout .hero-tag-reserve {{ display: grid; grid-template-columns: minmax(0, 1fr) 28px; grid-template-rows: repeat(3, 24px); gap: 5px 7px; min-height: 82px; }} body.official-card-layout .hero-tag-slot {{ grid-column: 1; }} body.official-card-layout .hero-tag-overflow {{ grid-column: 2; grid-row: 3; }}
    dialog {{ width: min(820px, calc(100% - 28px)); max-height: 88vh; overflow: auto; color: #edf2ff; background: #132038; border: 1px solid #516a93; border-radius: 14px; padding: 0; }} dialog::backdrop {{ background: rgb(0 0 0 / 65%); }}
    .detail {{ padding: 24px; }} .close {{ float: right; cursor: pointer; color: #dce8ff; background: transparent; border: 0; font-size: 26px; }} .detail-heading {{ display: flex; gap: 16px; align-items: center; padding-right: 34px; }} .detail-heading h2 {{ margin: 0; }} .hero-detail-header {{ position: sticky; top: 0; z-index: 1; display: flex; gap: 16px; align-items: center; width: calc(100% + 48px); margin: -24px -24px 18px; padding: 24px 58px 18px 24px; background: #132038; border-bottom: 1px solid #516a93; box-shadow: 0 5px 12px rgb(8 15 29 / 55%); }} .hero-detail-header .detail-close {{ position: absolute; top: 18px; right: 18px; z-index: 2; }} .hero-detail-header .detail-heading {{ flex: 1 1 280px; min-width: 0; padding-right: 0; }} .hero-detail-facts {{ display: grid; flex: 0 1 250px; grid-template-columns: repeat(2, minmax(105px, 1fr)); gap: 9px; }} .hero-detail-fact {{ min-width: 0; padding: 9px 11px; border-radius: 8px; background: #1c2b46; }} .hero-detail-fact strong {{ display: block; font-size: 22px; }} .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 9px; margin: 18px 0; }} .stat {{ background: #1c2b46; padding: 10px; border-radius: 8px; }} .skill {{ border-left: 3px solid #7aa6ff; background: #192942; padding: 12px; margin: 10px 0; white-space: pre-wrap; }} .upgrade {{ border-left-color: #f59e0b; }} .source {{ color: #fbbf24; font-size: 12px; margin-top: 6px; }}
    .status-detail {{ position: fixed; right: 24px; bottom: 24px; z-index: 3; width: min(620px, calc(100% - 28px)); max-height: min(560px, calc(100vh - 48px)); overflow: auto; color: #edf2ff; background: #132038; border: 1px solid #516a93; border-radius: 14px; box-shadow: 0 12px 32px rgb(0 0 0 / 45%); }} .status-term {{ cursor: pointer; border: 0; border-bottom: 1px dashed #8fb5ff; color: #a8c7ff; background: transparent; padding: 0; font: inherit; font-weight: 700; }} .status-term:hover, .status-term:focus {{ color: #d7e6ff; border-bottom-style: solid; }} .status-term-highlight {{ color: #c5d7ff; background: rgb(122 166 255 / 18%); border-radius: 3px; padding: 0 2px; font-weight: 700; }} .status-term-note {{ color: #b7c8e8; font-size: 0.92em; }} .status-content {{ margin: 16px 0 0; white-space: pre-wrap; line-height: 1.65; }}
    .empty {{ color: #a9b7cf; margin: 20px 0; }} @media (max-width: 1119px) {{ body.official-card-layout .results {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }} @media (max-width: 860px) {{ .controls {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .controls input {{ grid-column: span 2; }} body.official-card-layout .results {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }} @media (max-width: 600px) {{ input, select, .controls button {{ padding: 9px; font-size: 14px; }} body.official-card-layout .results {{ grid-template-columns: 1fr; }} body.official-card-layout .card-layout {{ grid-template-columns: 116px minmax(0, 1fr); gap: 14px; }} body.official-card-layout .portrait-block {{ min-height: 139px; }} body.official-card-layout .portrait-shell {{ width: 112px; height: 112px; }} body.official-card-layout .card-avatar {{ inset: 8px; }} body.official-card-layout .card-name {{ font-size: 22px; }} .tag-menu-level .tag-menu-level {{ position: static; width: auto; min-width: 0; margin-top: 8px; }} .hero-detail-header {{ flex-wrap: wrap; align-items: flex-start; }} .hero-detail-facts {{ width: 100%; flex-basis: 100%; }} .sort-selects {{ grid-template-columns: 1fr; gap: 6px; }} .sort-selects select, .sort-selects select:first-child, .sort-selects select + select {{ border: 1px solid #394867; border-radius: 9px; }} }}
  </style>
</head>
<body class="{'official-card-layout' if use_official_card_layout else ''}">
  <header><h1>Live A Hero 本地速查</h1><p id="snapshot"></p></header>
  <main>
    <section class="controls" aria-label="筛选条件">
      <input id="query" autofocus placeholder="搜索中文名、日文名、卡片编号或技能内容，例如：阿卡西">
      <label class="filter-control"><span class="control-label">分类</span><select id="kind"><option value="">全角色</option><option value="hero">仅英雄</option><option value="sidekick">仅助手</option></select></label>
      <section class="filter-control multi-select" id="rarity"><span class="control-label" id="rarity-label">稀有度</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="rarity-menu" aria-labelledby="rarity-label">全部</button><div class="multi-select-menu" id="rarity-menu" role="group" aria-labelledby="rarity-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select" id="element"><span class="control-label" id="element-label">属性</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="element-menu" aria-labelledby="element-label">全部</button><div class="multi-select-menu" id="element-menu" role="group" aria-labelledby="element-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select" id="role"><span class="control-label" id="role-label">职能</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="role-menu" aria-labelledby="role-label">全部</button><div class="multi-select-menu" id="role-menu" role="group" aria-labelledby="role-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select tag-select" id="hero-tags"><span class="control-label" id="hero-tags-label">英雄标签</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="hero-tags-menu" aria-labelledby="hero-tags-label">全部</button><div class="multi-select-menu" id="hero-tags-menu" role="group" aria-labelledby="hero-tags-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <section class="filter-control multi-select tag-select" id="assistant-tags"><span class="control-label" id="assistant-tags-label">助手标签</span><button class="multi-select-trigger" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="assistant-tags-menu" aria-labelledby="assistant-tags-label">全部</button><div class="multi-select-menu" id="assistant-tags-menu" role="group" aria-labelledby="assistant-tags-label" hidden><div class="multi-select-options"></div><button class="multi-select-clear" type="button">清空</button></div></section>
      <label class="filter-control sort-control"><span class="control-label">排序</span><span class="sort-selects"><select id="sortField" aria-label="排序依据"><option value="cardId">卡片 ID</option><option value="name">名称</option><option value="rarity">稀有度</option><option value="hp">HP</option><option value="attack">攻击</option><option value="agility">速度</option></select><select id="sortDirection" aria-label="排序顺序"><option value="asc">升序</option><option value="desc">降序</option></select></span></label>
{tag_settings_button}
    </section>
    <p class="summary" id="summary"></p><div class="groups" id="groups"></div>
  </main>
  <dialog id="detail"><div class="detail"><div id="detailContent"></div><section id="statusDetail" class="status-detail" hidden aria-labelledby="statusTitle"><div class="detail"><button class="close status-close" aria-label="关闭词条说明">×</button><h2 id="statusTitle"></h2><div class="status-content" id="statusContent"></div></div></section></div></dialog>
{tag_settings_dialog}
  <script>
    const catalog = {embedded_catalog};
    const avatarUrlPrefix = {json.dumps(avatar_url_prefix)};
    const localOfficialAssetPrefix = {json.dumps(local_official_asset_prefix)};
    const useOfficialCardLayout = {str(use_official_card_layout).lower()};
    const cards = catalog.cards;
    const assistantTags = catalog.assistantTags || [];
    const heroTags = catalog.heroTags || [];
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
    const frameAssetName = card => String(Math.min(3, Math.max(0, Number(displayRarity(card) || 1) - 2))).padStart(2, '0');
    function avatarMarkup(card, size) {{
      const avatar = card.avatar || {{status: 'missing', code: null}};
      const label = avatar.status === 'available' ? `${{card.name}} 头像` : `${{card.name}}（本地暂无头像）`;
      if (avatar.status !== 'available' || !avatar.code) return `<span class="avatar ${{size}} avatar-missing" role="img" aria-label="${{escape(label)}}" title="本地暂无头像">?</span>`;
      const filename = avatar.filename || `${{avatar.code}}.png`;
      const source = `${{avatarUrlPrefix}}/${{encodeURIComponent(filename)}}`;
      return `<span class="avatar ${{size}}"><img class="avatar-image" loading="lazy" src="${{escape(source)}}" alt="${{escape(label)}}"></span>`;
    }}
    function cardAvatarMarkup(card) {{
      const avatar = card.avatar || {{status: 'missing', code: null}};
      const label = avatar.status === 'available' ? `${{card.name}} 头像` : `${{card.name}}（本地暂无头像）`;
      if (avatar.status !== 'available' || !avatar.code) return `<span class="avatar card-avatar avatar-missing" role="img" aria-label="${{escape(label)}}" title="本地暂无头像">?</span>`;
      const filename = avatar.filename || `${{avatar.code}}.png`;
      const source = `${{avatarUrlPrefix}}/${{encodeURIComponent(filename)}}`;
      return `<span class="avatar card-avatar"><img class="avatar-image" loading="lazy" src="${{escape(source)}}" alt="${{escape(label)}}"></span>`;
    }}
    function cardFrameMarkup(card) {{
      const rarity = Math.min(5, Math.max(1, Number(displayRarity(card) || 1)));
      const frame = frameAssetName(card);
      const label = `${{rarity}}星${{kindLabel(card.kind)}}边框`;
      return localOfficialAssetPrefix
        ? `<img class="official-frame" loading="lazy" src="${{escape(`${{localOfficialAssetPrefix}}/hero-frame-${{frame}}.png`)}}" alt="${{escape(label)}}" onerror="useFrameFallback(this)">`
        : `<span class="official-frame official-frame-fallback" role="img" aria-label="${{escape(label)}}"></span>`;
    }}
    function useFrameFallback(image) {{
      const fallback = document.createElement('span');
      fallback.className = 'official-frame official-frame-fallback';
      fallback.setAttribute('role', 'img'); fallback.setAttribute('aria-label', image.alt || '星级边框');
      image.replaceWith(fallback);
    }}
    function roleBadgeMarkup(card) {{
      const role = card.kind === 'hero' ? 'hero' : 'sidekick';
      const label = kindLabel(card.kind);
      return localOfficialAssetPrefix
        ? `<span class="role-badge${{role === 'sidekick' ? ' sidekick' : ''}}"><img class="role-icon" loading="lazy" src="${{escape(`${{localOfficialAssetPrefix}}/role-${{role}}.png`)}}" alt="" onerror="useRoleAssetFallback(this)"><img class="role-wordmark" loading="lazy" src="${{escape(`${{localOfficialAssetPrefix}}/role-${{role}}-wordmark.png`)}}" alt="${{label}}" onerror="useRoleAssetFallback(this)"></span>`
        : `<span class="role-badge${{role === 'sidekick' ? ' sidekick' : ''}}"><span class="role-fallback">${{escape(label)}}</span></span>`;
    }}
    function useRoleAssetFallback(image) {{
      const badge = image.closest('.role-badge');
      if (!badge) return;
      const label = badge.classList.contains('sidekick') ? '助手' : '英雄';
      badge.replaceChildren(Object.assign(document.createElement('span'), {{className: 'role-fallback', textContent: label}}));
    }}
    function characterPortraitMarkup(card) {{
      return `<div class="portrait-block"><div class="portrait-shell">${{cardAvatarMarkup(card)}}${{cardFrameMarkup(card)}}</div>${{roleBadgeMarkup(card)}}</div>`;
    }}
    const elementAssetName = {{1: 'fire', 2: 'water', 3: 'earth', 4: 'light', 5: 'shadow'}};
    function heroMetadataMarkup(card) {{
      if (card.kind !== 'hero' || (!card.element?.label && !card.role?.label)) return '';
      const assetName = elementAssetName[card.element?.code];
      const element = card.element?.label
        ? (localOfficialAssetPrefix && assetName
          ? `<span class="hero-element"><img loading="lazy" src="${{escape(`${{localOfficialAssetPrefix}}/element-${{assetName}}.png`)}}" alt="${{escape(card.element.label)}}属性" data-element-label="${{escape(card.element.label)}}" onerror="useHeroElementFallback(this)"></span>`
          : `<span class="hero-element">${{escape(card.element.label)}}</span>`)
        : '';
      const role = card.role?.label ? `<span class="hero-role">${{escape(card.role.label)}}</span>` : '';
      const pinnedTags = (card.tags || []).filter(tag => tag.pinned);
      const tagReserve = `<div class="hero-tag-reserve">${{pinnedTags.slice(0, 3).map(tag => `<span class="tag hero-tag-slot">${{escape(tag.label)}}</span>`).join('')}}${{pinnedTags.length > 3 ? `<span class="tag hero-tag-overflow">+${{pinnedTags.length - 3}}</span>` : ''}}</div>`;
      return `<div class="hero-metadata"><div class="attribute-stack">${{element}}${{role}}</div>${{tagReserve}}</div>`;
    }}
    function useHeroElementFallback(image) {{
      const holder = image.closest('.hero-element');
      if (holder) holder.textContent = image.dataset.elementLabel || '?';
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
        const candidate = terms.find(item => text.startsWith(item.matchName || item.name, index));
        if (!candidate) {{ index += 1; continue; }}
        const matchedTerms = candidate.terms || [candidate];
        const status = matchedTerms[0];
        const matchedName = candidate.matchName || candidate.name;
        markup += escape(text.slice(textStart, index));
        if (matchedTerms.length === 1 && !seenNames.has(candidate.name)) {{
          markup += `<button class="status-term" type="button" data-status-id="${{escape(status.id)}}">${{escape(matchedName)}}</button>`;
          if (status.inlineDescription) markup += `<span class="status-term-note">（${{escape(status.inlineDescription)}}）</span>`;
        }} else {{
          markup += `<span class="status-term-highlight">${{escape(matchedName)}}</span>`;
        }}
        seenNames.add(candidate.name);
        index += matchedName.length; textStart = index;
      }}
      return markup + escape(text.slice(textStart));
    }}
    function descriptionMarkup(skill) {{
      return termMarkup(skill.description, skill.statusTerms || []);
    }}
    function sourceMarkup(skill) {{
      if (skill.descriptionSource === '部分日文回退') return '<div class="source">部分日文原文（官方简中未完整覆盖）</div>';
      if (skill.nameSource === '日文原文' || skill.descriptionSource === '日文原文') return '<div class="source">日文原文（官方简中未覆盖）</div>';
      return '';
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
    function setupTagSelector(id, tags) {{
      const control = $(id); const tagById = new Map(tags.map(tag => [tag.id, tag])); const selected = new Set(); let menuPath = [];
      const children = parentId => tags.filter(tag => tag.parentId === parentId);
      const updateLabel = () => {{ const labels = [...selected].map(tagId => tagById.get(tagId)?.label).filter(Boolean); control.querySelector('.multi-select-trigger').textContent = labels.length === 0 ? '全部' : labels.length === 1 ? labels[0] : `已选 ${{labels.length}} 项`; }};
      const renderLevel = (parentId, depth) => {{
        const level = document.createElement('div'); level.className = 'tag-menu-level';
        for (const tag of children(parentId)) {{
          if (children(tag.id).length) {{ const branch = document.createElement('button'); branch.type = 'button'; branch.className = `tag-menu-branch${{menuPath[depth] === tag.id ? ' is-active' : ''}}`; branch.textContent = tag.label; const open = event => {{ if (event.type === 'click') event.stopPropagation(); menuPath = [...menuPath.slice(0, depth), tag.id]; renderMenu(); }}; branch.addEventListener('mouseenter', open); branch.addEventListener('focus', open); branch.addEventListener('click', open); level.append(branch); continue; }}
          const label = document.createElement('label'); label.className = 'multi-select-option'; const input = document.createElement('input'); input.type = 'checkbox'; input.value = tag.id; input.checked = selected.has(tag.id); input.addEventListener('change', () => {{ if (input.checked) selected.add(tag.id); else selected.delete(tag.id); updateLabel(); render(); }}); label.append(input, document.createTextNode(tag.label)); level.append(label);
        }}
        const active = menuPath[depth]; if (active && children(active).length) level.append(renderLevel(active, depth + 1)); if (!level.childElementCount) level.textContent = '此分类下暂无可筛选标签。'; return level;
      }};
      const renderMenu = () => control.querySelector('.multi-select-options').replaceChildren(renderLevel(null, 0));
      control.querySelector('.multi-select-clear').addEventListener('click', () => {{ selected.clear(); updateLabel(); renderMenu(); render(); }}); renderMenu(); return selected;
    }}
    const selectedHeroTagIds = setupTagSelector('hero-tags', heroTags);
    const selectedAssistantTagIds = setupTagSelector('assistant-tags', assistantTags);
    $('snapshot').textContent = `快照：${{catalog.metadata.snapshotId}} · 英雄 ${{catalog.metadata.heroCardCount}} 张（仅 60 级属性）· 助手 ${{catalog.metadata.sidekickCardCount}} 张（最高技能阶段）· 技能强化 ${{catalog.metadata.skillUpgradeCount}} 项`;
    function matches(card) {{
      const query = $('query').value.trim().toLocaleLowerCase();
      const haystack = [card.name, card.originalName, card.cardId, ...card.aliases, ...card.skills.flatMap(skill => [skill.name, skill.originalName, skill.description]), ...(card.tags || []).map(tag => tag.label)].join('\\n').toLocaleLowerCase();
      const rarity = selectedValues('rarity'); const element = selectedValues('element'); const role = selectedValues('role'); const tags = card.kind === 'hero' ? selectedHeroTagIds : selectedAssistantTagIds;
      return (!query || haystack.includes(query)) && (!$('kind').value || card.kind === $('kind').value) && (!rarity.size || rarity.has('★'.repeat(displayRarity(card)))) && (!element.size || element.has(card.element?.label)) && (!role.size || role.has(card.role?.label)) && (!tags.size || [...tags].every(tagId => card.tags?.some(tag => tag.id === tagId)));
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
        for (const card of list) {{
          const button = document.createElement('button');
          button.className = `card${{useOfficialCardLayout && card.kind === 'hero' ? ' hero-card' : ''}}`;
          button.dataset.key = card.key;
          const sidekickTags = card.tags || [];
          const orderedSidekickTags = [...sidekickTags.filter(tag => tag.pinned), ...sidekickTags.filter(tag => !tag.pinned)];
          const legacyTags = card.kind === 'hero'
            ? [card.element?.label, card.role?.label, kindLabel(card.kind)]
            : [kindLabel(card.kind), ...orderedSidekickTags.slice(0, 3).map(tag => tag.label), ...(orderedSidekickTags.length > 3 ? [`+${{orderedSidekickTags.length - 3}}`] : [])];
          const sidekickTagLabels = orderedSidekickTags.map(tag => tag.label);
          const tags = card.kind === 'sidekick'
            ? (sidekickTagLabels.length <= 3
              ? sidekickTagLabels
              : [...sidekickTagLabels.slice(0, 3), `+${{sidekickTagLabels.length - 3}}`])
            : [];
          const tagsMarkup = tags.length ? `<div class="tags card-tags">${{tags.map(tag => `<span class="tag">${{escape(tag)}}</span>`).join('')}}</div>` : '';
          const officialCardIdentity = card.kind === 'hero'
            ? card.originalName
            : `${{card.originalName}} · #${{card.cardId}}`;
          const officialCardMarkup = `<div class="card-layout">${{characterPortraitMarkup(card)}}<div class="card-copy"><div class="name-copy"><h3 class="card-name">${{escape(card.name)}}</h3><p class="card-jp-name">${{escape(officialCardIdentity)}}</p></div>${{heroMetadataMarkup(card)}}${{tagsMarkup}}</div></div>`;
          const legacyCardMarkup = `<div class="card-layout">${{avatarMarkup(card, 'avatar-small')}}<div><div class="card-title"><span>${{escape(card.name)}}</span><span>${{escape('★'.repeat(displayRarity(card)))}}</span></div><div class="muted">${{escape(card.originalName)}} · #${{escape(card.cardId)}}</div><div class="tags">${{legacyTags.filter(Boolean).map(tag => `<span class="tag">${{escape(tag)}}</span>`).join('')}}</div></div></div>`;
          button.innerHTML = useOfficialCardLayout ? officialCardMarkup : legacyCardMarkup;
          grid.append(button);
        }}
        section.append(grid); groups.append(section);
      }}
      if (!result.length) groups.innerHTML = '<p class="empty">没有匹配项。可尝试角色日文名、卡片编号或技能文字。</p>';
    }}
    function showDetail(card) {{
      $('detail').classList.toggle('hero-detail', card.kind === 'hero');
      const stats = card.kind === 'hero'
        ? [['60级 HP',card.stats.level60.hp], ['60级 攻击',card.stats.level60.attack], ['60级 速度',card.stats.level60.agility]]
        : [['稀有度','★'.repeat(card.rarity)], ['满级 HP',card.stats.max.hp], ['满级 攻击',card.stats.max.attack], ['满级 速度',card.stats.max.agility]];
      const detailClose = '<button class="close detail-close" aria-label="关闭">×</button>';
      const heading = `<div class="detail-heading">${{avatarMarkup(card, 'avatar-large')}}<div><h2>${{escape(kindLabel(card.kind))}} · ${{escape(card.name)}}</h2><p class="muted">${{escape(card.originalName)}} · 卡片编号 #${{escape(card.cardId)}}${{card.kind === 'sidekick' ? ` · 最高技能阶段 ${{escape(card.skillLevel)}}` : ''}}</p></div></div>`;
      const heroHeader = card.kind === 'hero'
        ? `<div class="hero-detail-header">${{detailClose}}${{heading}}<div class="hero-detail-facts"><div class="hero-detail-fact"><div class="muted">属性</div><strong>${{escape(card.element?.label || '不适用')}}</strong></div><div class="hero-detail-fact"><div class="muted">职能</div><strong>${{escape(card.role?.label || '不适用')}}</strong></div></div></div>`
        : `${{detailClose}}${{heading}}`;
      const upgradeHtml = card.skillUpgrades.length ? `<h3>技能强化（独立记录）</h3>${{card.skillUpgrades.map(upgrade => `<article class="skill upgrade"><strong>${{escape(upgrade.before.name)}} → ${{escape(upgrade.after.name)}}</strong><div class="muted">技能 #${{escape(upgrade.before.skillId)}} → #${{escape(upgrade.after.skillId)}}${{upgrade.questId ? ` · 任务 #${{escape(upgrade.questId)}}` : ''}}</div><div><b>强化前：</b>${{descriptionMarkup(upgrade.before)}}</div><div><b>强化后（最高等级）：</b>${{descriptionMarkup(upgrade.after)}}</div>${{sourceMarkup(upgrade.after)}}</article>`).join('')}}` : '';
      const skillCostMarkup = skill => skill.viewCost != null ? `<div class="muted">消耗 View：${{escape(skill.viewCost)}}</div>` : '';
      const tagHtml = card.tags?.length ? `<h3>${{kindLabel(card.kind)}}标签</h3><div class="tags">${{card.tags.map(tag => `<span class="tag">${{escape(tag.path.join(' › '))}}</span>`).join('')}}</div>` : '';
      $('detailContent').innerHTML = `${{heroHeader}}<div class="stat-grid">${{stats.map(([label,value]) => `<div class="stat"><div class="muted">${{label}}</div><strong>${{escape(value ?? '—')}}</strong></div>`).join('')}}</div>${{tagHtml}}<h3>关联技能</h3>${{card.skills.map(skill => `<article class="skill"><strong>${{escape(skill.relation)}} · ${{escape(skill.name)}}</strong><div class="muted">${{escape(skill.originalName)}} · #${{escape(skill.skillId)}}</div>${{skillCostMarkup(skill)}}<div>${{descriptionMarkup(skill)}}</div>${{sourceMarkup(skill)}}</article>`).join('')}}${{upgradeHtml}}`;
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
{tag_settings_listeners}
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
    sidekick_avatars: dict[str, dict[str, str | None]] | None = None,
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
        card_status_terms = _status_terms_for_card(raw_card, status_terms)
        equipment_rows = (
            _sidekick_equipment_skill_rows(
                equipment_ids,
                append_ids,
                skills,
                localized,
                status_terms,
                card_status_terms,
            )
            if kind == "sidekick"
            else []
        )
        card_skills = [
            *[_skill_row(skill_id, "主动技能" if kind == "hero" else "主动技能（最高阶段）", skills, localized, status_terms, card_status_terms=card_status_terms) for skill_id in active_ids],
            *equipment_rows,
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
                "avatar": _avatar_for_card(
                    resource_name,
                    original_name,
                    name,
                    avatars,
                    sidekick_avatars if kind == "sidekick" else None,
                ),
                "rarity": raw_card.get("rarity", 0),
                "initialRarity": raw_card.get("initialRarity") if kind == "hero" else None,
                "element": _element(raw_card.get("element")) if kind == "hero" else None,
                "role": _role(raw_card.get("role")) if kind == "hero" else None,
                "stats": _stats(raw_card.get("growths") or [], kind),
                "skills": card_skills,
                "skillLevel": raw_card.get("levelZone") if kind == "sidekick" else None,
                "skillUpgrades": _skill_upgrades(raw_card, skills, localized, status_terms, card_status_terms) if kind == "hero" else [],
            }
        )
    return result


def _skill_row(
    skill_id: int | str,
    relation: str,
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
    card_status_terms: list[dict[str, str]] | None = None,
    description_override: str | None = None,
    description_source_override: str | None = None,
    official_chinese_availability_override: str | None = None,
    effects_override: list[dict[str, Any]] | None = None,
    status_term_skill_ids: list[int | str] | None = None,
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
    skill_status_terms = _status_terms_for_skill(
        skill_for_status_terms,
        cleaned_description,
        status_terms,
        card_status_terms,
        status_term_skill_ids,
    )
    return {
        "skillId": str(skill_id),
        "relation": relation,
        "viewCost": raw_skill.get("useView") if relation.startswith("主动技能") else None,
        "name": name,
        "nameSource": "官方简中" if localized.get(f"SKILL_NAME_{skill_id}") else "日文原文",
        "originalName": original_name,
        "description": cleaned_description,
        "descriptionSource": description_source,
        "officialChineseAvailability": official_chinese_availability_override or (
            "完整官方简中" if description_source == "官方简中" else "无官方简中"
        ),
        "statusTermSources": "、".join(
            sorted({term.get("source", "官方简中") for term in skill_status_terms})
        ) or "—",
        "statusTerms": skill_status_terms,
    }


def _sidekick_equipment_skill_rows(
    equipment_ids: list[int | str],
    append_ids: list[int | str],
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
    card_status_terms: list[dict[str, str]],
) -> list[dict[str, Any]]:
    highest_equipment_ids = _highest_skill_ids(equipment_ids)
    if not highest_equipment_ids:
        return []

    equipment_id = highest_equipment_ids[0]
    relation = "装备技能（最高等级）"
    equipment = _skill_row(
        equipment_id, relation, skills, localized, status_terms, card_status_terms
    )
    highest_append_ids = _highest_skill_ids(append_ids)
    if not highest_append_ids:
        return [equipment]

    append_id = highest_append_ids[0]
    append = _skill_row(append_id, relation, skills, localized, status_terms, card_status_terms)
    if not append["description"] or append["description"] == equipment["description"]:
        return [
            _skill_row(
                equipment_id,
                relation,
                skills,
                localized,
                status_terms,
                card_status_terms,
                effects_override=[
                    *(skills[str(equipment_id)].get("effects") or []),
                    *(skills[str(append_id)].get("effects") or []),
                ],
                status_term_skill_ids=[append_id],
            )
        ]

    sections = [
        ("装备效果", equipment["description"]),
        ("追加效果", append["description"]),
    ]
    description = "\n\n".join(f"【{label}】\n{text}" for label, text in sections if text)
    sources = [equipment["descriptionSource"], append["descriptionSource"]]
    all_official = all(source == "官方简中" for source in sources)
    any_official = any(source == "官方简中" for source in sources)
    return [
        _skill_row(
            equipment_id,
            relation,
            skills,
            localized,
            status_terms,
            card_status_terms,
            description_override=description,
            description_source_override=(
                "官方简中" if all_official else "部分日文回退" if any_official else "日文原文"
            ),
            official_chinese_availability_override=(
                "完整官方简中" if all_official else "部分官方简中" if any_official else "无官方简中"
            ),
            effects_override=[
                *(skills[str(equipment_id)].get("effects") or []),
                *(skills[str(append_id)].get("effects") or []),
            ],
            status_term_skill_ids=[append_id],
        )
    ]


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
    sidekick_avatars: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, str | None]:
    avatar = (sidekick_avatars or {}).get(resource_name.lower()) or avatars["code"].get(
        resource_name.lower()
    ) or avatars["jp"].get(
        _canonical_character_name(original_name)
    ) or avatars["cn"].get(
        _canonical_character_name(localized_name)
    )
    return dict(avatar) if avatar else {"status": "missing", "code": None}


def _sidekick_avatar_overrides(
    icon_dir: Path, overrides_path: Path | None
) -> dict[str, dict[str, str | None]]:
    if not overrides_path or not overrides_path.is_file():
        return {}
    overrides = _read_json(overrides_path)
    if not isinstance(overrides, dict):
        return {}

    result = {}
    for resource_name, filename in overrides.items():
        if not isinstance(resource_name, str) or not isinstance(filename, str):
            continue
        if Path(filename).name != filename or not (icon_dir / filename).is_file():
            continue
        result[resource_name.lower()] = {
            "status": "available",
            "code": resource_name,
            "filename": filename,
        }
    return result


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
    card_status_terms: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not raw_card.get("hasSkillUpgrade"):
        return []

    active_skills = raw_card.get("skillProvider", {}).get("activeSkills", [])
    base_skills = sorted(
        (item for item in active_skills if item.get("skillUpgrade") == 0),
        key=lambda item: item.get("skillLearnNo", 0),
    )
    upgraded_skills = sorted(
        (item for item in active_skills if item.get("skillUpgrade") == 1),
        key=lambda item: item.get("skillLearnNo", 0),
    )
    if len(base_skills) != 3 or len(upgraded_skills) != 3:
        return []

    quest = next(iter(raw_card.get("skillUpgradeQuestInfos") or []), {})
    quest_id = str(quest["questId"]) if quest.get("questId") is not None else None
    return [
        {
            "skillLevel": quest.get("skillUpgrade"),
            "questId": quest_id,
            "before": _skill_row(
                before["skillId"],
                f"技能 {before['skillLearnNo']}",
                skills,
                localized,
                status_terms,
                card_status_terms,
            ),
            "after": _highest_upgrade_skill_row(
                after["skillId"], skills, localized, status_terms, card_status_terms
            ),
        }
        for before, after in zip(base_skills, upgraded_skills, strict=True)
    ]


def _highest_upgrade_skill_row(
    skill_id: int | str,
    skills: dict[str, dict[str, Any]],
    localized: dict[str, str],
    status_terms: dict[str, dict[str, str]],
    card_status_terms: list[dict[str, str]],
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
        return _skill_row(skill_id, "强化后", skills, localized, status_terms, card_status_terms)

    highest_effects = [
        max(effects, key=lambda effect: (effect.get("conditionPriority", 0), effect.get("serialNo", 0)))
        for effects in condition_groups.values()
    ]
    highest_effects = _remove_subsumed_highest_effects(highest_effects)
    highest_effects.sort(key=lambda effect: effect.get("serialNo", 0))
    base_description = _clean_text(raw_skill.get("description", ""))
    localized_base_description = _clean_text(localized.get(f"SKILL_DESCRIPTION_{skill_id}", ""))
    condition_parts = [
        _upgrade_condition_part(skill_id, effect, localized)
        for effect in highest_effects
    ]
    prefix_parts = [part for part in condition_parts if part[2]]
    suffix_parts = [part for part in condition_parts if not part[2]]
    final_description = "\n".join(
        part
        for part in [
            *(part[0] for part in prefix_parts),
            localized_base_description or base_description,
            *(part[0] for part in suffix_parts),
        ]
        if part
    )
    all_official = bool(localized_base_description) and all(part[1] for part in condition_parts)
    any_official = bool(localized_base_description) or any(part[1] for part in condition_parts)
    description_source = "官方简中" if all_official else "部分日文回退" if any_official else "日文原文"
    return _skill_row(
        skill_id,
        "强化后",
        skills,
        localized,
        status_terms,
        card_status_terms,
        description_override=final_description,
        description_source_override=description_source,
        official_chinese_availability_override=(
            "完整官方简中" if all_official else "部分官方简中" if any_official else "无官方简中"
        ),
        effects_override=[*base_effects, *highest_effects],
    )


def _remove_subsumed_highest_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    effect_ids = {effect.get("skillEffectId") for effect in effects}
    subsumed = set().union(
        *(subsumed_ids for all_id, subsumed_ids in SUBSUMED_HIGHEST_EFFECT_IDS.items() if all_id in effect_ids)
    ) if effect_ids else set()
    return [effect for effect in effects if effect.get("skillEffectId") not in subsumed]


def _upgrade_condition_part(
    skill_id: int | str, effect: dict[str, Any], localized: dict[str, str]
) -> tuple[str, bool, bool]:
    serial_no = effect.get("serialNo", 0)
    override = UPGRADE_CONDITION_TEXT_OVERRIDES.get((str(skill_id), serial_no))
    localized_text = _clean_text(
        localized.get(f"SKILL_EFFECT_CONDITION_DESCRIPTION_{skill_id}_{serial_no}", "")
    )
    text = override or localized_text or _clean_text(effect.get("conditionDescription", ""))
    return text, bool(override or localized_text), bool(override)


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
                "source": "官方简中",
            }
    result["all"] = {**result["effect"], **result["skill"]}
    for terms in SPECIAL_STATUS_TERMS_BY_SKILL.values():
        for term in terms:
            result["all"][term["id"]] = dict(term)
    return result


def _status_terms_for_card(
    raw_card: dict[str, Any], status_terms: dict[str, dict[str, dict[str, str]]]
) -> list[dict[str, str]]:
    stock_id = str(raw_card.get("stockId") or "")
    if not stock_id:
        return []
    return [term for status_id, term in status_terms["skill"].items() if status_id.startswith(stock_id)]


def _status_terms_for_skill(
    raw_skill: dict[str, Any],
    description: str,
    status_terms: dict[str, dict[str, dict[str, str]]],
    card_status_terms: list[dict[str, str]] | None = None,
    status_term_skill_ids: list[int | str] | None = None,
) -> list[dict[str, str]]:
    candidates: dict[str, dict[str, dict[str, str]]] = {}
    def add(status_term: dict[str, str] | None) -> None:
        if status_term and (status_term.get("matchName") or status_term["name"]) in description:
            candidates.setdefault(status_term["name"], {})[status_term["id"]] = status_term

    for effect in raw_skill.get("effects") or []:
        add(status_terms["effect"].get(str(effect.get("skillEffectId"))))
    skill_ids = [raw_skill.get("skillId"), *(status_term_skill_ids or [])]
    for skill_id in skill_ids:
        add(status_terms["skill"].get(str(skill_id)))
    for status_term in card_status_terms or []:
        if status_term and status_term["name"] not in candidates:
            add(status_term)
    for skill_id in skill_ids:
        for status_term in SPECIAL_STATUS_TERMS_BY_SKILL.get(str(skill_id), []):
            if (status_term.get("matchName") or status_term["name"]) in description:
                candidates[status_term["name"]] = {status_term["id"]: dict(status_term)}
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
    parser.add_argument("--assistant-tags", type=Path, default=DEFAULT_ASSISTANT_TAGS_PATH)
    parser.add_argument("--hero-tags", type=Path, default=DEFAULT_HERO_TAGS_PATH)
    parser.add_argument("--xlsx", type=Path, help="同时导出 Excel 工作簿")
    parser.add_argument(
        "--node",
        default=str(CODEX_NODE_PATH) if CODEX_NODE_PATH.is_file() else shutil.which("node") or "node",
    )
    args = parser.parse_args()
    catalog = build_catalog(
        args.snapshot_dir,
        assistant_tags_path=args.assistant_tags,
        hero_tags_path=args.hero_tags,
    )
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
