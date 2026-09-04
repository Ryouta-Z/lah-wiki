"""Local-only administrator page for independent Live A Hero card tags."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

try:
    from scripts.assistant_tags import (
        DEFAULT_ASSISTANT_TAGS_PATH,
        delete_tag,
        read_assistant_tag_config,
        reorder_tag_siblings,
        validate_assistant_tag_config,
        write_assistant_tag_config,
    )
    from scripts.lah_quickref import DEFAULT_CATALOG_PATH, rebuild_quickref
    from scripts.hero_tags import (
        DEFAULT_HERO_TAGS_PATH,
        delete_tag as delete_hero_tag,
        read_hero_tag_config,
        reorder_tag_siblings as reorder_hero_tag_siblings,
        validate_hero_tag_config,
        write_hero_tag_config,
    )
except ModuleNotFoundError:  # Allow `python scripts/assistant_tag_admin.py` from the project root.
    from assistant_tags import (  # type: ignore[no-redef]
        DEFAULT_ASSISTANT_TAGS_PATH,
        delete_tag,
        read_assistant_tag_config,
        reorder_tag_siblings,
        validate_assistant_tag_config,
        write_assistant_tag_config,
    )
    from lah_quickref import DEFAULT_CATALOG_PATH, rebuild_quickref  # type: ignore[no-redef]
    from hero_tags import (  # type: ignore[no-redef]
        DEFAULT_HERO_TAGS_PATH,
        delete_tag as delete_hero_tag,
        read_hero_tag_config,
        reorder_tag_siblings as reorder_hero_tag_siblings,
        validate_hero_tag_config,
        write_hero_tag_config,
    )


LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def _read_catalog() -> dict[str, Any]:
    with DEFAULT_CATALOG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _cards(kind: str) -> list[dict[str, Any]]:
    return sorted(
        (card for card in _read_catalog()["cards"] if card["kind"] == kind),
        key=lambda card: (card["name"], card["cardId"]),
    )


def _mode(mode: str) -> dict[str, Any]:
    modes = {
        "hero": {"kind": "hero", "label": "英雄", "read": read_hero_tag_config, "write": write_hero_tag_config, "validate": validate_hero_tag_config, "delete": delete_hero_tag, "reorder": reorder_hero_tag_siblings, "path": DEFAULT_HERO_TAGS_PATH},
        "assistant": {"kind": "sidekick", "label": "助手", "read": read_assistant_tag_config, "write": write_assistant_tag_config, "validate": validate_assistant_tag_config, "delete": delete_tag, "reorder": reorder_tag_siblings, "path": DEFAULT_ASSISTANT_TAGS_PATH},
    }
    if mode not in modes:
        raise ValueError(f"未知标签模式：{mode}")
    return modes[mode]


def _state(mode: str) -> dict[str, Any]:
    definition = _mode(mode)
    cards = _cards(definition["kind"])
    config = definition["validate"](definition["read"](definition["path"]), {card["key"] for card in cards})
    return {"mode": mode, "label": definition["label"], "config": config, "cards": cards}


def _save_and_rebuild(mode: str, config: dict[str, Any]) -> dict[str, Any]:
    definition = _mode(mode)
    validated = definition["validate"](config, {card["key"] for card in _cards(definition["kind"])})
    definition["write"](definition["path"], validated)
    rebuild_quickref()
    return validated


def _detail(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


def _admin_page() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live A Hero 标签管理</title>
  <style>
    :root { color-scheme: dark; font-family: "Microsoft YaHei UI", system-ui, sans-serif; background: #101827; color: #e6edf8; }
    * { box-sizing: border-box; } body { margin: 0; } header { padding: 24px 32px; background: linear-gradient(130deg, #1d4ed8, #7c3aed); } h1 { margin: 0; font-size: 26px; } header p { margin: 7px 0 0; color: #dbeafe; }
    main { display: grid; grid-template-columns: minmax(240px, .8fr) minmax(300px, 1fr) minmax(360px, 1.4fr); gap: 16px; width: min(1440px, calc(100% - 32px)); margin: 22px auto 40px; align-items: start; }
    section { border: 1px solid #31425f; border-radius: 12px; background: #162238; padding: 16px; } h2 { margin: 0 0 12px; font-size: 18px; } h3 { margin: 16px 0 8px; font-size: 15px; color: #c9d8f3; } label { display: grid; gap: 5px; margin: 10px 0; color: #b9c7df; font-size: 13px; font-weight: 700; }
    input, select, button { width: 100%; border: 1px solid #394867; border-radius: 8px; padding: 9px; color: #edf2ff; background: #172235; font: inherit; } button { cursor: pointer; } button:hover, button:focus { border-color: #77a5ff; background: #1b2c49; } button.secondary { background: #1c2b46; } button.danger { border-color: #a65368; color: #ffd5dd; background: #412133; } .row { display: flex; gap: 8px; } .row > * { flex: 1; } .mode-switch { display: flex; gap: 7px; width: auto; } .mode-switch button { width: auto; } .mode-switch button.active { border-color: #dbeafe; background: #29456f; }
    .tree { display: grid; gap: 3px; max-height: 390px; overflow: auto; } .tree button { border: 0; border-radius: 6px; text-align: left; padding: 7px; background: transparent; } .tree button.selected { background: #29456f; } .tree-row { display: flex; align-items: center; gap: 2px; border-radius: 6px; } .tree-row > button:last-child { flex: 1; } .tree-children { margin-left: 14px; padding-left: 8px; border-left: 1px solid #415779; }
    .assistant-list { display: grid; gap: 4px; max-height: 520px; overflow: auto; } .assistant-list button { text-align: left; } .assistant-list button.selected { border-color: #77a5ff; background: #1b2c49; } .muted { color: #a9b7cf; font-size: 13px; line-height: 1.55; } .notice { min-height: 20px; color: #fcd34d; font-size: 13px; }
    .tag-menu { position: relative; display: grid; gap: 8px; } .tag-root-row, .tag-popup-branch { display: flex; align-items: center; gap: 4px; border: 1px solid #394867; border-radius: 8px; background: #172235; } .tag-root-toggle, .tag-popup-toggle { display: flex; width: 100%; align-items: center; gap: 8px; border: 0; text-align: left; } .tag-root-toggle { padding: 10px; font-weight: 700; } .tag-popup-toggle { padding: 8px; font-weight: 700; } .tag-root-toggle::after, .tag-popup-toggle::after { content: "▸"; color: #9ab8ef; } .tag-root-row.active { border-color: #77a5ff; background: #1b2c49; } .tag-count { margin-left: auto; color: #a9b7cf; font-size: 12px; font-weight: 400; white-space: nowrap; } .tag-popup { position: absolute; z-index: 20; display: grid; gap: 6px; width: min(340px, calc(100vw - 24px)); max-height: min(360px, calc(100vh - 24px)); overflow: auto; padding: 8px; border: 1px solid #77a5ff; border-radius: 10px; background: #142038; box-shadow: 0 14px 32px #060b16aa; } .tag-popup .tag-option { margin: 0; } .tag-popup-branch { padding: 0; } .tag-option { display: flex; gap: 10px; align-items: center; margin: 0; padding: 8px; border: 1px solid #394867; border-radius: 7px; font-weight: 400; cursor: pointer; } .tag-option:hover { border-color: #77a5ff; background: #1b2c49; } .tag-option input { width: 22px; height: 22px; flex: 0 0 22px; margin: 0; padding: 0; cursor: pointer; } .tag-option input:disabled { cursor: not-allowed; } .tag-option-label { flex: 1; min-width: 0; } .pinned-tags { display: grid; gap: 6px; } .pinned-tags:empty::before { content: "请先在上方选择叶子标签。"; color: #a9b7cf; font-size: 13px; } .drag-handle { width: auto; flex: 0 0 auto; padding: 5px 7px; border: 0; color: #9ab8ef; background: transparent; cursor: grab; line-height: 1; touch-action: none; } .drag-handle:active { cursor: grabbing; } .dragging { opacity: .45; } .drop-before { box-shadow: inset 0 3px #77a5ff; } .drop-after { box-shadow: inset 0 -3px #77a5ff; } .skills { display: grid; gap: 8px; max-height: 330px; overflow: auto; } .skill { border-left: 3px solid #7aa6ff; padding: 9px; background: #192942; white-space: pre-wrap; } .skill strong { display: block; margin-bottom: 4px; }
    @media (max-width: 1050px) { main { grid-template-columns: 1fr 1fr; } main > section:last-child { grid-column: span 2; } } @media (max-width: 650px) { main { display: grid; grid-template-columns: 1fr; width: min(100% - 20px, 620px); } main > section:last-child { grid-column: auto; } header { padding: 20px; } }
  </style>
</head>
<body>
  <header><div class="row"><div><h1 id="pageTitle">英雄标签管理</h1><p>仅本机可访问。每次保存都会立即更新公共标签并重新生成离线速查页。</p></div><div class="mode-switch"><button id="heroMode" class="active" type="button">英雄</button><button id="assistantMode" type="button">助手</button></div></div></header>
  <main>
    <section><h2>标签树</h2><div id="tagTree" class="tree"></div><div class="row"><button id="newRoot" class="secondary" type="button">新增根标签</button><button id="newChild" class="secondary" type="button">新增子标签</button></div><form id="tagForm"><h3 id="tagFormTitle">新建根标签</h3><label>标签名称<input id="tagLabel" required maxlength="60"></label><label>上级标签<select id="tagParent"></select></label><div class="row"><button type="submit">保存标签</button><button id="deleteTag" class="danger" type="button" hidden>删除标签</button></div></form><p id="tagNotice" class="notice"></p></section>
    <section><h2 id="listTitle">英雄</h2><label id="queryLabel">搜索英雄<input id="assistantQuery" placeholder="名称、日文名或卡片编号"></label><label class="tag-option"><input id="onlyUntagged" type="checkbox"><span id="untaggedLabel">仅显示未标注英雄</span></label><div id="assistantList" class="assistant-list"></div></section>
    <section><h2 id="editorTitle">选择一名英雄</h2><p id="editorHint" class="muted">选择英雄后，可查看全部关联技能和技能强化，并勾选叶子标签。</p><div id="assignmentEditor" hidden><div id="assignmentTags" class="tag-options"></div><h3 id="pinnedTagsTitle">置顶标签（0/3）</h3><p class="muted">置顶只影响卡片显示顺序，不会改变标签样式或标签树排序。</p><div id="pinnedTags" class="pinned-tags"></div><button id="saveAssignment" type="button">保存此英雄的标签</button><h3>关联技能</h3><div id="skills" class="skills"></div></div><p id="assignmentNotice" class="notice"></p></section>
  </main>
  <script>
    const $ = id => document.getElementById(id);
    let state = null; let mode = 'hero'; let selectedTagId = null; let selectedCardKey = null; let draggedTag = null; let reordering = false; let assignmentDraftTagIds = null; let assignmentDraftPinnedTagIds = null; let activeMenuPath = [];
    const api = async (url, options = {}) => {
      let response;
      try {
        response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
      } catch (_) {
        throw new Error('无法连接本机管理服务。请保持启动窗口开启，刷新页面后重试。');
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : (data.detail?.message || '保存失败')); error.detail = data.detail; throw error; }
      return data;
    };
    const tagById = () => new Map(state.config.tags.map(tag => [tag.id, tag]));
    const children = parentId => state.config.tags.filter(tag => tag.parentId === parentId);
    const pathFor = tagId => { const tag = tagById().get(tagId); return tag?.parentId ? [...pathFor(tag.parentId), tag.label] : tag ? [tag.label] : []; };
    const setNotice = (id, message = '') => { $(id).textContent = message; };
    const clearDropMarkers = () => document.querySelectorAll('.drop-before, .drop-after').forEach(item => item.classList.remove('drop-before', 'drop-after'));
    const currentAssignmentDraft = () => assignmentDraftTagIds ? new Set(assignmentDraftTagIds) : selectedCardKey ? new Set(state.config.assignments[selectedCardKey] || []) : null;
    const siblingOrder = (parentId, movingId, targetId, after) => {
      const tagIds = children(parentId).map(tag => tag.id); if (movingId === targetId) return tagIds;
      tagIds.splice(tagIds.indexOf(movingId), 1); const targetIndex = tagIds.indexOf(targetId); tagIds.splice(targetIndex + (after ? 1 : 0), 0, movingId); return tagIds;
    };
    async function saveTagOrder(parentId, movingId, targetId, after, noticeId) {
      const tagIds = siblingOrder(parentId, movingId, targetId, after);
      if (tagIds.every((tagId, index) => tagId === children(parentId)[index].id) || reordering) return;
      const draft = currentAssignmentDraft(); const menuPath = [...activeMenuPath]; reordering = true; setNotice(noticeId, '正在保存排序…');
      try {
        const result = await api(`/api/${mode}/tags/order`, {method: 'PUT', body: JSON.stringify({parentId, tagIds})}); state.config = result.config;
        renderTree(); renderTagForm(); renderAssistantList(); renderAssignmentEditor(draft, menuPath, assignmentDraftPinnedTagIds); setNotice(noticeId, '排序已保存并发布。');
      } catch (error) { setNotice(noticeId, error.message); }
      finally { reordering = false; clearDropMarkers(); }
    }
    function makeSortable(target, tag, parentId, noticeId) {
      const handle = document.createElement('button'); handle.type = 'button'; handle.className = 'drag-handle'; handle.draggable = true; handle.title = '拖动调整同级顺序'; handle.setAttribute('aria-label', `拖动 ${tag.label} 调整同级顺序`); handle.textContent = '⠿'; target.prepend(handle);
      handle.addEventListener('click', event => event.stopPropagation());
      handle.addEventListener('dragstart', event => { draggedTag = {id: tag.id, parentId}; target.classList.add('dragging'); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', tag.id); });
      handle.addEventListener('dragend', () => { draggedTag = null; target.classList.remove('dragging'); clearDropMarkers(); });
      target.addEventListener('dragover', event => {
        if (!draggedTag || draggedTag.parentId !== parentId || draggedTag.id === tag.id) return;
        event.preventDefault(); const after = event.clientY > target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2; clearDropMarkers(); target.classList.add(after ? 'drop-after' : 'drop-before'); event.dataTransfer.dropEffect = 'move';
      });
      target.addEventListener('dragleave', () => target.classList.remove('drop-before', 'drop-after'));
      target.addEventListener('drop', event => {
        if (!draggedTag || draggedTag.parentId !== parentId || draggedTag.id === tag.id) return;
        event.preventDefault(); const after = event.clientY > target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2; void saveTagOrder(parentId, draggedTag.id, tag.id, after, noticeId);
      });
    }
    function renderTree() {
      const tree = $('tagTree'); tree.replaceChildren();
      const renderBranch = parentId => {
        const holder = document.createElement('div');
        for (const tag of children(parentId)) {
          const row = document.createElement('div'); row.className = 'tree-row'; const button = document.createElement('button'); button.type = 'button'; button.textContent = tag.label;
          button.classList.toggle('selected', tag.id === selectedTagId); button.addEventListener('click', () => { selectedTagId = tag.id; renderTagForm(); renderTree(); }); row.append(button); makeSortable(row, tag, parentId, 'tagNotice'); holder.append(row);
          const nested = renderBranch(tag.id); if (nested.childElementCount) { nested.className = 'tree-children'; holder.append(nested); }
        }
        return holder;
      };
      tree.append(renderBranch(null));
    }
    function renderParentOptions() {
      const select = $('tagParent'); select.replaceChildren();
      select.append(new Option('顶层标签', ''));
      for (const tag of state.config.tags) {
        if (tag.id === selectedTagId) continue;
        select.append(new Option(pathFor(tag.id).join(' › '), tag.id));
      }
    }
    function renderTagForm(parentId = null) {
      renderParentOptions(); const tag = tagById().get(selectedTagId);
      $('tagFormTitle').textContent = tag ? `编辑标签：${pathFor(tag.id).join(' › ')}` : '新建标签';
      $('tagLabel').value = tag?.label || ''; $('tagParent').value = tag ? (tag.parentId || '') : (parentId || ''); $('deleteTag').hidden = !tag;
    }
    function renderAssistantList() {
      const query = $('assistantQuery').value.trim().toLocaleLowerCase(); const untagged = $('onlyUntagged').checked;
      const assignments = state.config.assignments; const list = $('assistantList'); list.replaceChildren();
      for (const card of state.cards.filter(card => {
        const text = [card.name, card.originalName, card.cardId].join(' ').toLocaleLowerCase();
        return (!query || text.includes(query)) && (!untagged || !(assignments[card.key] || []).length);
      })) {
        const button = document.createElement('button'); button.type = 'button'; button.classList.toggle('selected', card.key === selectedCardKey);
        button.textContent = `${card.name} · ★${card.rarity} · #${card.cardId}${(assignments[card.key] || []).length ? ` · 已标 ${assignments[card.key].length}` : ''}`;
        button.addEventListener('click', () => { selectedCardKey = card.key; assignmentDraftTagIds = null; assignmentDraftPinnedTagIds = null; activeMenuPath = []; renderAssignmentEditor(); renderAssistantList(); }); list.append(button);
      }
    }
    function renderAssignmentEditor(draftTagIds = null, menuPath = [], draftPinnedTagIds = null) {
      const card = state.cards.find(item => item.key === selectedCardKey); const editor = $('assignmentEditor');
      editor.hidden = !card; if (!card) { $('editorTitle').textContent = `选择一名${state.label}`; return; }
      $('editorTitle').textContent = `${card.name} · #${card.cardId}`; assignmentDraftTagIds = new Set(draftTagIds || assignmentDraftTagIds || state.config.assignments[card.key] || []); assignmentDraftPinnedTagIds = new Set(draftPinnedTagIds || assignmentDraftPinnedTagIds || state.config.pinnedAssignments[card.key] || []); const tags = $('assignmentTags'); tags.replaceChildren(); tags.className = 'tag-menu';
      const leavesBelow = tagId => { const nested = children(tagId); return nested.length ? nested.flatMap(child => leavesBelow(child.id)) : [tagById().get(tagId)]; };
      const selectedCount = tag => leavesBelow(tag.id).filter(leaf => assignmentDraftTagIds.has(leaf.id)).length;
      const countLabel = tag => { const count = selectedCount(tag); return count ? `已选 ${count}` : `${leavesBelow(tag.id).length} 个标签`; };
      const closeTagMenus = () => { tags.querySelectorAll('.tag-popup').forEach(menu => menu.remove()); tags.querySelectorAll('.tag-root-row.active').forEach(row => row.classList.remove('active')); activeMenuPath = []; };
      const placeMenu = (menu, anchor, side) => {
        menu.style.visibility = 'hidden'; tags.append(menu); const tagRect = tags.getBoundingClientRect(); const anchorRect = anchor.getBoundingClientRect(); const menuRect = menu.getBoundingClientRect();
        const menuGap = 16; let left = side === 'below' ? anchorRect.left - tagRect.left : anchorRect.right - tagRect.left + menuGap; let top = side === 'below' ? anchorRect.bottom - tagRect.top + menuGap : anchorRect.top - tagRect.top;
        if (side !== 'below' && anchorRect.right + 8 + menuRect.width > window.innerWidth) left = anchorRect.left - tagRect.left - menuRect.width - 8;
        if (top + tagRect.top + menuRect.height > window.innerHeight - 8) top = Math.max(8 - tagRect.top, window.innerHeight - tagRect.top - menuRect.height - 8);
        menu.style.left = `${left}px`; menu.style.top = `${top}px`; menu.style.visibility = '';
        if (side === 'below' && menu.getBoundingClientRect().top < anchorRect.bottom + menuGap) menu.style.top = `${top + anchorRect.bottom + menuGap - menu.getBoundingClientRect().top}px`;
      };
      const findMenuItem = (holder, tagId) => [...holder.querySelectorAll('[data-tag-id]')].find(item => item.dataset.tagId === tagId);
      const showMenu = (tag, anchor, depth) => {
        if (activeMenuPath[depth] === tag.id) { tags.querySelectorAll('.tag-popup').forEach(menu => { if (Number(menu.dataset.depth) >= depth) menu.remove(); }); if (!depth) anchor.classList.remove('active'); activeMenuPath = activeMenuPath.slice(0, depth); return; }
        tags.querySelectorAll('.tag-popup').forEach(menu => { if (Number(menu.dataset.depth) >= depth) menu.remove(); }); activeMenuPath = [...activeMenuPath.slice(0, depth), tag.id];
        if (!depth) { tags.querySelectorAll('.tag-root-row.active').forEach(row => row.classList.remove('active')); anchor.classList.add('active'); }
        const menu = document.createElement('div'); menu.className = 'tag-popup'; menu.dataset.depth = depth; menu.dataset.parentId = tag.id;
        for (const child of children(tag.id)) {
          const nested = children(child.id);
          if (nested.length) {
            const branch = document.createElement('div'); branch.className = 'tag-popup-branch'; branch.dataset.tagId = child.id; const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'tag-popup-toggle'; const name = document.createElement('span'); name.textContent = child.label; const count = document.createElement('span'); count.className = 'tag-count'; count.textContent = countLabel(child); toggle.append(name, count); toggle.addEventListener('click', () => showMenu(child, branch, depth + 1)); branch.append(toggle); makeSortable(branch, child, tag.id, 'assignmentNotice'); menu.append(branch); continue;
          }
          const option = document.createElement('div'); option.className = 'tag-option'; option.dataset.tagId = child.id; const input = document.createElement('input'); input.type = 'checkbox'; input.value = child.id; input.setAttribute('aria-label', child.label); input.checked = assignmentDraftTagIds.has(child.id); input.addEventListener('change', () => { if (input.checked) assignmentDraftTagIds.add(child.id); else { assignmentDraftTagIds.delete(child.id); assignmentDraftPinnedTagIds.delete(child.id); } renderAssignmentEditor(assignmentDraftTagIds, activeMenuPath, assignmentDraftPinnedTagIds); }); const label = document.createElement('span'); label.className = 'tag-option-label'; label.textContent = child.label; option.addEventListener('click', event => { if (event.target === input || event.target.closest('.drag-handle')) return; input.click(); }); option.append(input, label); makeSortable(option, child, tag.id, 'assignmentNotice'); menu.append(option);
        }
        placeMenu(menu, anchor, depth === 0 ? 'below' : 'side');
      };
      for (const tag of children(null)) {
        if (!children(tag.id).length) {
          const option = document.createElement('div'); option.className = 'tag-option'; option.dataset.tagId = tag.id; const input = document.createElement('input'); input.type = 'checkbox'; input.value = tag.id; input.setAttribute('aria-label', tag.label); input.checked = assignmentDraftTagIds.has(tag.id); input.addEventListener('change', () => { if (input.checked) assignmentDraftTagIds.add(tag.id); else { assignmentDraftTagIds.delete(tag.id); assignmentDraftPinnedTagIds.delete(tag.id); } renderAssignmentEditor(assignmentDraftTagIds, activeMenuPath, assignmentDraftPinnedTagIds); }); const label = document.createElement('span'); label.className = 'tag-option-label'; label.textContent = tag.label; option.addEventListener('click', event => { if (event.target === input || event.target.closest('.drag-handle')) return; input.click(); }); option.append(input, label); makeSortable(option, tag, null, 'assignmentNotice'); tags.append(option); continue;
        }
        const row = document.createElement('div'); row.className = 'tag-root-row'; row.dataset.tagId = tag.id; const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'tag-root-toggle'; const name = document.createElement('span'); name.textContent = tag.label; const count = document.createElement('span'); count.className = 'tag-count'; count.textContent = countLabel(tag); toggle.append(name, count); toggle.addEventListener('click', () => showMenu(tag, row, 0)); row.append(toggle); makeSortable(row, tag, null, 'assignmentNotice'); tags.append(row);
      }
      activeMenuPath = [...menuPath];
      if (activeMenuPath.length) requestAnimationFrame(() => {
        const path = [...activeMenuPath]; activeMenuPath = [];
        for (let depth = 0; depth < path.length; depth += 1) {
          const tag = tagById().get(path[depth]); const holder = depth ? tags.querySelector(`.tag-popup[data-depth="${depth - 1}"]`) : tags; const anchor = holder && findMenuItem(holder, tag.id); if (!tag || !anchor) break; showMenu(tag, anchor, depth);
        }
      });
      const pinnedTags = $('pinnedTags'); pinnedTags.replaceChildren();
      const selectedLeaves = []; const appendSelectedLeaves = parentId => { for (const tag of children(parentId)) { const nested = children(tag.id); if (nested.length) appendSelectedLeaves(tag.id); else if (assignmentDraftTagIds.has(tag.id)) selectedLeaves.push(tag); } }; appendSelectedLeaves(null);
      for (const tag of selectedLeaves) {
        const option = document.createElement('label'); option.className = 'tag-option'; const input = document.createElement('input'); input.type = 'checkbox'; input.value = tag.id; input.checked = assignmentDraftPinnedTagIds.has(tag.id); input.disabled = !input.checked && assignmentDraftPinnedTagIds.size >= 3; input.setAttribute('aria-label', `置顶 ${tag.label}`); input.addEventListener('change', () => { if (input.checked) assignmentDraftPinnedTagIds.add(tag.id); else assignmentDraftPinnedTagIds.delete(tag.id); renderAssignmentEditor(assignmentDraftTagIds, activeMenuPath, assignmentDraftPinnedTagIds); }); const label = document.createElement('span'); label.className = 'tag-option-label'; label.textContent = tag.label; option.append(input, label); pinnedTags.append(option);
      }
      $('pinnedTagsTitle').textContent = `置顶标签（${assignmentDraftPinnedTagIds.size}/3）`;
      const skills = $('skills'); skills.replaceChildren(); for (const skill of card.skills) { const article = document.createElement('article'); article.className = 'skill'; const title = document.createElement('strong'); title.textContent = `${skill.relation} · ${skill.name}`; const body = document.createElement('div'); body.textContent = skill.description; article.append(title, body); skills.append(article); } for (const upgrade of card.skillUpgrades || []) { const article = document.createElement('article'); article.className = 'skill'; const title = document.createElement('strong'); title.textContent = `技能强化 · ${upgrade.before.name} → ${upgrade.after.name}`; const body = document.createElement('div'); body.textContent = `强化前：${upgrade.before.description}\n强化后：${upgrade.after.description}`; article.append(title, body); skills.append(article); }
      $('assignmentEditor').onpointerdown = event => event.stopPropagation();
      document.onpointerdown = event => { if (!event.target.closest('#assignmentTags')) closeTagMenus(); };
      document.onkeydown = event => { if (event.key === 'Escape') closeTagMenus(); };
    }
    function renderMode() { const label = mode === 'hero' ? '英雄' : '助手'; $('pageTitle').textContent = `${label}标签管理`; $('listTitle').textContent = label; $('queryLabel').firstChild.textContent = `搜索${label}`; $('untaggedLabel').textContent = `仅显示未标注${label}`; $('editorHint').textContent = mode === 'hero' ? '选择英雄后，可查看全部关联技能和技能强化，并勾选叶子标签。' : '选择助手后，可查看保留技能并勾选叶子标签。'; $('saveAssignment').textContent = `保存此${label}的标签`; $('heroMode').classList.toggle('active', mode === 'hero'); $('assistantMode').classList.toggle('active', mode === 'assistant'); }
    async function refresh(keepSelection = true) { state = await api(`/api/${mode}/state`); if (keepSelection && selectedTagId && !tagById().has(selectedTagId)) selectedTagId = null; if (keepSelection && selectedCardKey && !state.cards.some(card => card.key === selectedCardKey)) selectedCardKey = null; renderMode(); renderTree(); renderTagForm(); renderAssistantList(); renderAssignmentEditor(); }
    $('newRoot').addEventListener('click', () => { selectedTagId = null; renderTree(); renderTagForm(); $('tagLabel').focus(); });
    $('newChild').addEventListener('click', () => { if (!selectedTagId) return setNotice('tagNotice', '请先从标签树选择一个父级。'); const parent = selectedTagId; selectedTagId = null; renderTree(); renderTagForm(parent); $('tagLabel').focus(); });
    $('tagForm').addEventListener('submit', async event => { event.preventDefault(); setNotice('tagNotice'); const payload = {label: $('tagLabel').value, parentId: $('tagParent').value || null}; try { if (selectedTagId) await api(`/api/${mode}/tags/${encodeURIComponent(selectedTagId)}`, {method: 'PATCH', body: JSON.stringify(payload)}); else { payload.id = `tag-${crypto.randomUUID()}`; await api(`/api/${mode}/tags`, {method: 'POST', body: JSON.stringify(payload)}); } await refresh(false); setNotice('tagNotice', '标签已保存并发布。'); } catch (error) { setNotice('tagNotice', error.message); } });
    $('deleteTag').addEventListener('click', async () => { if (!selectedTagId) return; try { await api(`/api/${mode}/tags/${encodeURIComponent(selectedTagId)}`, {method: 'DELETE'}); } catch (error) { const message = error.detail?.message || error.message; if (!error.detail || !confirm(`${message}；确认后将永久删除。`)) return setNotice('tagNotice', message); try { await api(`/api/${mode}/tags/${encodeURIComponent(selectedTagId)}?confirm=true`, {method: 'DELETE'}); selectedTagId = null; await refresh(false); setNotice('tagNotice', '标签已删除并发布。'); } catch (confirmedError) { setNotice('tagNotice', confirmedError.message); } } });
    $('assistantQuery').addEventListener('input', renderAssistantList); $('onlyUntagged').addEventListener('change', renderAssistantList);
    $('saveAssignment').addEventListener('click', async () => { if (!selectedCardKey) return; setNotice('assignmentNotice'); const tagIds = [...(assignmentDraftTagIds || [])]; const pinnedTagIds = [...(assignmentDraftPinnedTagIds || [])]; try { await api(`/api/${mode}/cards/${encodeURIComponent(selectedCardKey)}/tags`, {method: 'PUT', body: JSON.stringify({tagIds, pinnedTagIds})}); assignmentDraftTagIds = null; assignmentDraftPinnedTagIds = null; activeMenuPath = []; await refresh(); setNotice('assignmentNotice', `${state.label}标签已保存并发布。`); } catch (error) { setNotice('assignmentNotice', error.message); } });
    for (const [button, nextMode] of [['heroMode', 'hero'], ['assistantMode', 'assistant']]) $(button).addEventListener('click', () => { if (mode === nextMode) return; mode = nextMode; selectedTagId = null; selectedCardKey = null; assignmentDraftTagIds = null; assignmentDraftPinnedTagIds = null; activeMenuPath = []; refresh(false).catch(error => setNotice('tagNotice', error.message)); });
    refresh().catch(error => setNotice('tagNotice', error.message));
  </script>
</body>
</html>"""


def create_app() -> FastAPI:
    app = FastAPI(title="Live A Hero 标签管理", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _admin_page()

    @app.get("/api/{mode}/state")
    def get_state(mode: str) -> dict[str, Any]:
        try:
            return _state(mode)
        except ValueError as error:
            raise _detail(error) from error

    @app.post("/api/{mode}/tags")
    def create_tag(mode: str, tag: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = _mode(mode)
            config = definition["read"](definition["path"])
            config["tags"].append({"id": tag.get("id"), "label": tag.get("label"), "parentId": tag.get("parentId")})
            return {"config": _save_and_rebuild(mode, config)}
        except ValueError as error:
            raise _detail(error) from error

    @app.put("/api/{mode}/tags/order")
    def reorder_tags(mode: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = _mode(mode)
            config = definition["read"](definition["path"])
            definition["reorder"](config, body.get("parentId"), body.get("tagIds"))
            return {"config": _save_and_rebuild(mode, config)}
        except ValueError as error:
            raise _detail(error) from error

    @app.patch("/api/{mode}/tags/{tag_id}")
    def update_tag(mode: str, tag_id: str, update: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = _mode(mode)
            config = definition["read"](definition["path"])
            tag = next((item for item in config["tags"] if item["id"] == tag_id), None)
            if tag is None:
                raise ValueError(f"标签不存在：{tag_id}")
            tag["label"] = update.get("label")
            tag["parentId"] = update.get("parentId")
            return {"config": _save_and_rebuild(mode, config)}
        except ValueError as error:
            raise _detail(error) from error

    @app.delete("/api/{mode}/tags/{tag_id}")
    def remove_tag(mode: str, tag_id: str, confirm: bool = False) -> dict[str, Any]:
        try:
            definition = _mode(mode)
            config = definition["read"](definition["path"])
            prospective = deepcopy(config)
            removed_ids = definition["delete"](prospective, tag_id)
            affected = sum(bool(set(tag_ids) & removed_ids) for tag_ids in config["assignments"].values())
            if not confirm:
                raise HTTPException(
                    status_code=409,
                    detail={"message": f"将删除 {len(removed_ids)} 个标签，并清除 {affected} 名{definition['label']}的归属。", "affected": affected},
                )
            return {"config": _save_and_rebuild(mode, prospective), "affected": affected}
        except HTTPException:
            raise
        except ValueError as error:
            raise _detail(error) from error

    @app.put("/api/{mode}/cards/{card_key}/tags")
    def update_assignment(mode: str, card_key: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = _mode(mode)
            config = definition["read"](definition["path"])
            tag_ids = body.get("tagIds")
            pinned_tag_ids = body.get("pinnedTagIds", [])
            if tag_ids:
                config["assignments"][card_key] = tag_ids
            else:
                config["assignments"].pop(card_key, None)
            if pinned_tag_ids:
                config["pinnedAssignments"][card_key] = pinned_tag_ids
            else:
                config["pinnedAssignments"].pop(card_key, None)
            return {"config": _save_and_rebuild(mode, config)}
        except ValueError as error:
            raise _detail(error) from error

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="启动仅本机访问的英雄和助手标签管理页")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=LOCAL_HOST, port=args.port)


if __name__ == "__main__":
    main()
