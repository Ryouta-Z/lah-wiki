(() => {
  const header = document.querySelector('header');
  const access = document.querySelector('.wiki-update-access');
  if (header && access) header.append(access);
  const requiredIds = [
    'wiki-update-meta', 'wiki-update-dialog', 'wiki-update-entry', 'wiki-update-show',
    'wiki-update-title', 'wiki-update-time', 'wiki-update-topic', 'wiki-update-summary',
    'wiki-update-dont-remind', 'wiki-update-state', 'wiki-update-dismiss',
    'wiki-update-notes', 'wiki-update-read'
  ];
  const elements = Object.fromEntries(requiredIds.map(id => [id, document.getElementById(id)]));
  if (requiredIds.some(id => !elements[id])) return;
  let metadata;
  try { metadata = JSON.parse(elements['wiki-update-meta'].textContent); }
  catch { return; }
  const latest = metadata.latest;
  if (!latest || !/^[a-f0-9]{40}$/.test(latest.pushSha)) return;

  const dialog = elements['wiki-update-dialog'];
  if (typeof dialog.showModal !== 'function') return;
  const checkbox = elements['wiki-update-dont-remind'];
  const state = elements['wiki-update-state'];
  const entry = elements['wiki-update-entry'];
  const reminderVersion = typeof metadata.releaseVersion === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(metadata.releaseVersion)
    ? metadata.releaseVersion : latest.pushSha;
  const preferenceKey = 'lah-wiki-update:suppressed:' + reminderVersion;
  let suppressed = false;
  let storageAvailable = true;
  try { suppressed = localStorage.getItem(preferenceKey) === '1'; }
  catch { storageAvailable = false; }

  elements['wiki-update-title'].textContent = metadata.activityName;
  elements['wiki-update-time'].textContent = '当前更新：' + latest.pushedAtBeijing.slice(0, 19).replace('T', ' ').replaceAll('-', '.') + '（北京时间）';
  elements['wiki-update-topic'].textContent = latest.title;
  elements['wiki-update-summary'].textContent = latest.summary;
  const notesHref = entry.dataset.wikiUpdateBase + '/' + latest.notesPath + '#' + latest.notesAnchor;
  entry.href = elements['wiki-update-notes'].href = notesHref;

  function updateStorageState() {
    state.hidden = storageAvailable;
    state.textContent = storageAvailable ? '' : '浏览器无法保存提醒偏好，重新打开时仍会提示。';
    checkbox.disabled = !storageAvailable;
  }
  function showReminder() {
    checkbox.checked = suppressed;
    if (!dialog.open) dialog.showModal();
  }
  dialog.addEventListener('close', () => {
    try {
      if (checkbox.checked) {
        localStorage.setItem(preferenceKey, '1');
        suppressed = true;
      } else if (suppressed) {
        localStorage.removeItem(preferenceKey);
        suppressed = false;
      }
    } catch { storageAvailable = false; }
    updateStorageState();
    entry.focus();
  });
  ['wiki-update-dismiss', 'wiki-update-read', 'wiki-update-notes'].forEach(id => {
    elements[id].addEventListener('click', () => dialog.close());
  });
  elements['wiki-update-show'].addEventListener('click', showReminder);
  updateStorageState();
  if (!suppressed || new URLSearchParams(location.search).get('reminder') === 'show') showReminder();
})();
