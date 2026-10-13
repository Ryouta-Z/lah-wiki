function cardReleaseMarkup(card) {
  const release = card.history?.release;
  return `<div class="lah-card-release"><strong>${escape(release?.version || '版本待补')}</strong><time${release?.date ? ` datetime="${escape(release.date)}"` : ''}>${release?.date ? escape(release.date.replaceAll('-', '.')) : '日期待补'}</time></div>`;
}

function historySourceMarkup(event) {
  return `<div class="lah-history-sources">${(event?.sources || []).map(source => `<a href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.label)}</a>`).join('')}</div>`;
}

function historyTreeMarkup(card) {
  if (!card.skillUpgrades?.length) return '';
  return `<details class="lah-history-tree"><summary>展开现行满强化内容 · ${card.skillUpgrades.length} 个技能</summary><p class="lah-history-note">对比技能树强化前与当前资料收录的满强化效果；不代表仅解锁第一个节点的数值。</p>${card.skillUpgrades.map(upgrade => `<article class="lah-history-upgrade"><strong>${escape(upgrade.before.relation)} · ${escape(upgrade.before.name)}</strong><div class="lah-history-compare"><div><b>强化前</b><div>${descriptionMarkup(upgrade.before)}</div>${sourceMarkup(upgrade.before)}</div><div><b>强化后（最高等级）</b><div>${descriptionMarkup(upgrade.after)}</div>${sourceMarkup(upgrade.after)}</div></div></article>`).join('')}</details>`;
}

function historyPanelMarkup(card, scope = 'current') {
  const history = card.history || {};
  const release = history.release;
  const family = (history.familyCardKeys || [card.key]).map(key => byId.get(key)).filter(Boolean);
  const base = byId.get(history.baseCardKey);
  const related = family.filter(item => item.history?.variantKind === 'sp');
  const dateLabel = date => date ? date.replaceAll('-', '.') : '日期待补';
  const timeline = (scope === 'all' ? family : [card]).flatMap(item => {
    const ownRelease = item.history?.release;
    const kind = item.kind === 'sidekick' ? '助手' : item.history?.variantKind === 'sp' ? 'SP 英雄' : item.history?.variantKind === 'custom' ? '自定义卡' : '英雄';
    return [
      {type: 'release', card: item, ...ownRelease, title: `${item.name} · ${kind}上线`},
      ...(item.history?.events || []).map(event => ({...event, card: item, title: `${item.name} · 技能树开放`}))
    ];
  }).sort((a, b) => (a.date || '9999').localeCompare(b.date || '9999') || a.card.key.localeCompare(b.card.key));
  const treeHasEvent = (history.events || []).some(event => event.type === 'tree');
  return `<div class="lah-history-release"><strong>${escape(release?.version || '版本待补')}</strong><time${release?.date ? ` datetime="${escape(release.date)}"` : ''}>${escape(dateLabel(release?.date))}</time><span>首次上线</span></div><p class="lah-history-context">${escape(release?.context || '上线资料尚待核对')}</p>${release?.note || release?.versionNote ? `<p class="lah-history-release-note">${escape([release.note, release.versionNote].filter(Boolean).join(' '))}</p>` : ''}
    <div class="lah-history-section"><h3>${card.kind === 'sidekick' ? '同角色的 SP 英雄' : '本体与 SP'}</h3></div>
    ${related.length ? `<div class="lah-history-variants">${related.map(sp => `<div class="lah-history-variant">${avatarMarkup(sp, 'lah-history-avatar')}<div><button type="button" class="lah-history-card-link" data-history-card="${escape(sp.key)}">${escape(sp.name)}</button><p>${escape(sp.history.release?.version || '版本待补')} · ${escape(dateLabel(sp.history.release?.date))}${sp.key === card.key ? ' · 当前卡片' : ''}</p></div><div class="lah-history-gap"><span>距本体上线</span>${sp.history.daysFromBase != null ? ` <strong>${escape(sp.history.daysFromBase)}</strong> 天` : ' 待计算'}</div></div>`).join('')}</div><p class="lah-history-note">${base ? `以<button type="button" class="lah-history-card-link" data-history-card="${escape(base.key)}">${escape(base.name)}本体英雄</button> ${escape(dateLabel(base.history?.release?.date))} 为起点，逐张计算日期差。` : '本体上线日期核实后计算间隔。'}${card.kind === 'sidekick' ? '此处为关联英雄记录。' : ''}</p>` : `<p class="lah-history-empty">${history.variantKind === 'custom' || history.variantKind === 'soldier' ? '这张卡不参与本体与 SP 间隔计算。' : '当前资料中没有关联的 SP 英雄。'}</p>`}
    <div class="lah-history-section"><h3>历史时间线</h3><div class="lah-history-scope" aria-label="历史范围"><button type="button" data-history-scope="current" aria-pressed="${scope === 'current'}">当前卡片</button><button type="button" data-history-scope="all" aria-pressed="${scope === 'all'}">同角色全部</button></div></div>
    <ol class="lah-history-timeline">${timeline.map(event => `<li class="lah-history-event ${event.type}"><div class="lah-history-date"><time${event.date ? ` datetime="${escape(event.date)}"` : ''}>${escape(dateLabel(event.date))}</time><strong>${escape(event.version || '版本待补')}</strong></div><div class="lah-history-event-content"><strong>${escape(event.title)}</strong><p class="lah-history-context">${escape(event.context || '资料待补')}</p>${event.note || event.versionNote ? `<p class="lah-history-note">${escape([event.note, event.versionNote].filter(Boolean).join(' '))}</p>` : ''}${historySourceMarkup(event)}${event.type === 'tree' ? historyTreeMarkup(event.card) : ''}</div></li>`).join('')}</ol>
    ${card.kind === 'hero' && !treeHasEvent ? card.skillUpgrades?.length ? `<div class="lah-history-unconfirmed"><p>已收录技能树内容，开放日期及客户端版本尚待核实。</p>${historyTreeMarkup(card)}</div>` : '<p class="lah-history-unconfirmed">暂未收录这张卡的技能树历史，后续按来源补齐。</p>' : ''}
    <p class="lah-history-footer">日期按日区首次可获取的自然日计算。复刻、升星不重算 SP 间隔。资料核对：${escape(catalog.metadata.cardHistory?.verifiedAt || '待补')}。</p>`;
}

function renderCardHistoryDetail(card) {
  const content = $('detailContent');
  const skillsPanel = document.createElement('div');
  skillsPanel.id = 'lah-skills-panel';
  skillsPanel.setAttribute('role', 'tabpanel');
  skillsPanel.setAttribute('aria-labelledby', 'lah-skills-tab');
  const children = [...content.children];
  const headerCount = card.kind === 'hero' ? 1 : 2;
  for (const child of children.slice(headerCount)) skillsPanel.append(child);
  const tabs = document.createElement('div');
  tabs.className = 'lah-detail-tabs';
  tabs.setAttribute('role', 'tablist');
  tabs.setAttribute('aria-label', '详情内容');
  tabs.innerHTML = '<button id="lah-skills-tab" type="button" role="tab" aria-selected="true" aria-controls="lah-skills-panel">技能资料</button><button id="lah-history-tab" type="button" role="tab" aria-selected="false" aria-controls="lah-history-panel" tabindex="-1">历史记录</button>';
  const historyPanel = document.createElement('div');
  historyPanel.id = 'lah-history-panel';
  historyPanel.className = 'lah-history-panel';
  historyPanel.setAttribute('role', 'tabpanel');
  historyPanel.setAttribute('aria-labelledby', 'lah-history-tab');
  historyPanel.dataset.cardKey = card.key;
  historyPanel.hidden = true;
  historyPanel.innerHTML = historyPanelMarkup(card);
  content.append(tabs, skillsPanel, historyPanel);
}

function selectCardDetailTab(name, focus = false) {
  for (const tabName of ['skills', 'history']) {
    const tab = $('lah-' + tabName + '-tab');
    tab.setAttribute('aria-selected', String(tabName === name));
    tab.tabIndex = tabName === name ? 0 : -1;
    $('lah-' + tabName + '-panel').hidden = tabName !== name;
  }
  $('statusDetail').hidden = true;
  if (focus) $('lah-' + name + '-tab').focus({preventScroll: true});
}

document.addEventListener('click', event => {
  const tab = event.target.closest('#lah-skills-tab, #lah-history-tab');
  if (tab) selectCardDetailTab(tab.id === 'lah-history-tab' ? 'history' : 'skills');
  const scope = event.target.closest('[data-history-scope]');
  if (scope) {
    const panel = $('lah-history-panel');
    panel.innerHTML = historyPanelMarkup(byId.get(panel.dataset.cardKey), scope.dataset.historyScope);
    panel.querySelector(`[data-history-scope="${scope.dataset.historyScope}"]`).focus({preventScroll: true});
  }
  const link = event.target.closest('[data-history-card]');
  if (link) {
    const card = byId.get(link.dataset.historyCard);
    if (!card) return;
    showDetail(card);
    selectCardDetailTab('history', true);
    $('detail').scrollTop = 0;
  }
});

document.addEventListener('keydown', event => {
  const tab = event.target.closest('#lah-skills-tab, #lah-history-tab');
  if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const name = event.key === 'Home' ? 'skills' : event.key === 'End' ? 'history' : tab.id === 'lah-skills-tab' ? 'history' : 'skills';
  selectCardDetailTab(name, true);
});
