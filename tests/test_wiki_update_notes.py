import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.lah_quickref import ROOT, _include_update_notes, render_static_html, write_static_site


def empty_catalog():
    return {
        "metadata": {}, "cards": [], "heroTags": [], "assistantTags": [],
        "statusTerms": [], "skills": [], "skillUpgrades": [],
    }


class WikiUpdateNotesRenderTest(unittest.TestCase):
    def test_reminder_keeps_catalog_and_existing_query_layout(self):
        catalog = empty_catalog()
        page = render_static_html(catalog, include_tag_settings=False)
        embedded = re.search(r"(?m)^    const catalog = (.*);$", page)
        self.assertEqual(json.loads(embedded[1]), catalog)
        self.assertIn('<p id="snapshot"></p>', page)
        self.assertIn('id="query" autofocus', page)
        self.assertIn('id="wiki-update-dialog"', page)
        self.assertIn('id="wiki-update-meta"', page)
        self.assertIn('id="wiki-update-script"', page)
        self.assertNotIn("__UPDATE_NOTES_BASE__", page)
        self.assertNotIn("__WIKI_UPDATE_META_JSON__", page)
        self.assertNotIn("fetch(", page)
        header = re.search(r"<header>(.*?)</header>", page, re.S)[1]
        self.assertNotIn("wiki-update-access", header)
        self.assertRegex(page, r"</header>\s*<!-- wiki-update:access:start -->")
        self.assertNotIn("<dialog", header)

    def test_notes_base_is_relative_and_attribute_escaped(self):
        page = render_static_html(empty_catalog(), update_notes_base='../notes & "history"/')
        self.assertIn('../notes &amp; &quot;history&quot;/20261008-heroes-blues.html', page)
        self.assertNotIn('__UPDATE_NOTES_BASE__', page)

    def test_existing_custom_interface_is_preserved_without_duplicate_reminders(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            old_catalog = empty_catalog()
            old_catalog["metadata"] = {"snapshot": "old"}
            page = render_static_html(old_catalog).replace(
                "    const catalog =", "    // 查询界面层：已保留定制控件\n    const catalog ="
            ).replace("</main>", '<div id="custom-query-interface">原查询界面</div></main>')
            path.write_text(page, encoding="utf-8")
            catalog = empty_catalog()
            catalog["metadata"] = {"snapshot": "new"}
            write_static_site(catalog, path)
            write_static_site(catalog, path)
            updated = path.read_text(encoding="utf-8")
        self.assertIn('id="custom-query-interface">原查询界面', updated)
        self.assertIn("// 查询界面层：已保留定制控件", updated)
        self.assertEqual(json.loads(re.search(r"(?m)^    const catalog = (.*);$", updated)[1]), catalog)
        for identifier in ("wiki-update-style", "wiki-update-dialog", "wiki-update-meta", "wiki-update-script"):
            self.assertEqual(updated.count(f'id="{identifier}"'), 1)

    def test_rebuilding_migrates_legacy_header_entry_without_duplicates(self):
        page = render_static_html(empty_catalog(), include_tag_settings=False)
        block = re.search(r"<!-- wiki-update:access:start -->.*?<!-- wiki-update:access:end -->\n?", page, re.S)[0]
        legacy = page.replace(block, "").replace("</header>", block + "</header>", 1)
        updated = _include_update_notes(_include_update_notes(legacy, "更新笔记"), "更新笔记")
        self.assertNotIn("wiki-update-access", re.search(r"<header>(.*?)</header>", updated, re.S)[1])
        self.assertRegex(updated, r"</header>\s*<!-- wiki-update:access:start -->")
        self.assertEqual(updated.count('id="wiki-update-entry"'), 1)
        self.assertEqual(updated.count('id="wiki-update-show"'), 1)

    def test_metadata_cannot_break_out_of_json_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / "quickref" / "更新笔记"
            notes.mkdir(parents=True)
            meta = {"activityName": "测试</script><script>坏内容\u2028\u2029"}
            (notes / "update-meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            (notes / "reminder.html").write_text(
                '<a href="__UPDATE_NOTES_BASE__/notes.html">更新笔记</a>'
                '<!-- UPDATE_NOTES_DIALOG -->'
                '<script type="application/json" id="wiki-update-meta">__WIKI_UPDATE_META_JSON__</script>',
                encoding="utf-8",
            )
            (notes / "reminder.css").write_text("", encoding="utf-8")
            (notes / "reminder.js").write_text("", encoding="utf-8")
            with patch("scripts.lah_quickref.ROOT", root):
                page = _include_update_notes("<html><head></head><body><header></header></body></html>", "更新笔记")
        embedded = re.search(r'<script type="application/json" id="wiki-update-meta">(.*?)</script>', page, re.S)[1]
        self.assertEqual(json.loads(embedded), meta)
        self.assertNotIn("</script>", embedded)
        self.assertNotIn("\u2028", embedded)
        self.assertNotIn("\u2029", embedded)

    def test_portable_owner_controls_filter_keeps_reminder(self):
        page = render_static_html(empty_catalog())
        public = "\n".join(line for line in page.splitlines() if "tagSettings" not in line and ".tag-settings-close" not in line)
        self.assertIn('id="wiki-update-dialog"', public)
        self.assertIn('id="wiki-update-script"', public)
        self.assertIn('id="wiki-update-meta"', public)
        self.assertNotIn('id="tagSettings"', public)
        self.assertNotIn('id="tagSettingsDetail"', public)


@unittest.skipUnless(shutil.which("node"), "Node.js required for reminder event checks")
class WikiUpdateNotesReminderTest(unittest.TestCase):
    def run_reminder(self, *, storage=None, query="", actions=None, metadata=None, blocked=False, rebuild_header=False, legacy_header=False):
        page = render_static_html(empty_catalog(), include_tag_settings=False)
        header_replacement = ""
        if rebuild_header:
            page = _include_update_notes((ROOT / "quickref/index.html").read_text(encoding="utf-8"), "更新笔记")
            header_replacement = re.search(r"(?m)^    document\.querySelector\('header'\)\.innerHTML = .*;$", page)[0]
        if legacy_header:
            block = re.search(r"<!-- wiki-update:access:start -->.*?<!-- wiki-update:access:end -->\n?", page, re.S)[0]
            page = page.replace(block, "").replace("</header>", block + "</header>", 1)
        header_html = re.search(r"<header\b[^>]*>(.*?)</header>", page, re.S)[1]
        access_html = re.search(r'<nav class="wiki-update-access".*?</nav>', page, re.S)[0]
        script = re.search(r'<script id="wiki-update-script">(.*?)</script>', page, re.S)[1]
        meta = metadata or json.loads((ROOT / "quickref/更新笔记/update-meta.json").read_text(encoding="utf-8"))
        program = r"""
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const storage = {...input.storage};
const mutations = [];
let focused = null;
function element(id) { return {
  textContent: '', hidden: false, checked: false, disabled: false, open: false,
  dataset: {}, events: {}, parentNode: null, children: [],
  addEventListener(type, listener) { (this.events[type] ||= []).push(listener); },
  fire(type) { for (const listener of this.events[type] || []) listener({type}); },
  focus() { focused = id; },
  showModal() { this.open = true; },
  close() { if (this.open) { this.open = false; this.fire('close'); } }
}; }
const elements = Object.fromEntries(input.ids.map(id => [id, element(id)]));
let accessPresent = true;
const body = {children: []};
const access = {children: input.accessIds.map(id => elements[id]), parentNode: body};
const header = {
  children: input.headerIds.filter(id => !input.accessIds.includes(id)).map(id => elements[id]),
  append(node) {
    if (node.parentNode) node.parentNode.children = node.parentNode.children.filter(child => child !== node);
    node.parentNode = this;
    this.children.push(node);
  },
  set innerHTML(value) {
    function remove(node) {
      if (node === access) accessPresent = false;
      for (const child of node.children) remove(child);
      for (const id of Object.keys(elements)) if (elements[id] === node) delete elements[id];
      node.parentNode = null;
    }
    for (const child of this.children) remove(child);
    this.children = [];
    for (const match of value.matchAll(/id="([^"]+)"/g)) {
      const node = elements[match[1]] = element(match[1]);
      node.parentNode = this;
      this.children.push(node);
    }
  }
};
for (const child of header.children) child.parentNode = header;
for (const child of access.children) child.parentNode = access;
if (input.accessInside) header.append(access);
else body.children.push(access);
const document = {
  getElementById: id => elements[id] || null,
  querySelector: selector => selector === 'header' ? header : selector === '.wiki-update-access' && accessPresent ? access : null
};
elements['wiki-update-meta'].textContent = JSON.stringify(input.meta);
elements['wiki-update-entry'].dataset.wikiUpdateBase = '更新笔记';
const context = {
  document, $: id => document.getElementById(id), escape: value => value,
  location: {search: input.query}, URLSearchParams,
  localStorage: {
    getItem(key) { if (input.blocked) throw Error('blocked'); return storage[key] ?? null; },
    setItem(key, value) { if (input.blocked) throw Error('blocked'); storage[key] = value; mutations.push(['set', key, value]); },
    removeItem(key) { if (input.blocked) throw Error('blocked'); delete storage[key]; mutations.push(['remove', key]); }
  }
};
if (input.headerReplacement) vm.runInNewContext(input.headerReplacement, context);
const afterRebuild = {
  entryExists: document.getElementById('wiki-update-entry') !== null,
  showExists: document.getElementById('wiki-update-show') !== null
};
vm.runInNewContext(input.script, context);
const initial = {open: elements['wiki-update-dialog'].open,
  checked: elements['wiki-update-dont-remind'].checked, mutations: [...mutations]};
for (const action of input.actions) {
  if (action.type === 'check') elements['wiki-update-dont-remind'].checked = action.checked;
  else if (action.type === 'close') elements['wiki-update-dialog'].close();
  else elements[action.id].fire('click');
}
process.stdout.write(JSON.stringify({initial, storage, mutations, focused,
  afterRebuild, accessInHeader: accessPresent && access.parentNode === header,
  entryInHeader: elements['wiki-update-entry']?.parentNode === access && access.parentNode === header,
  showInHeader: elements['wiki-update-show']?.parentNode === access && access.parentNode === header,
  open: elements['wiki-update-dialog'].open,
  checked: elements['wiki-update-dont-remind'].checked,
  disabled: elements['wiki-update-dont-remind'].disabled,
  state: elements['wiki-update-state'].textContent,
  title: elements['wiki-update-title'].textContent,
  notes: elements['wiki-update-entry']?.href}));
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", program],
            input=json.dumps({"script": script, "meta": meta, "ids": re.findall(r'id="([^"]+)"', page),
                              "headerIds": re.findall(r'id="([^"]+)"', header_html),
                              "accessIds": re.findall(r'id="([^"]+)"', access_html),
                              "accessInside": "wiki-update-access" in header_html, "headerReplacement": header_replacement,
                              "storage": storage or {}, "query": query, "actions": actions or [], "blocked": blocked}),
            text=True, capture_output=True, encoding="utf-8", check=True,
        )
        return json.loads(result.stdout), meta

    def test_actual_query_header_rebuild_keeps_both_entries_and_opens_reminder(self):
        result, meta = self.run_reminder(rebuild_header=True)
        self.assertEqual(result["afterRebuild"], {"entryExists": True, "showExists": True})
        self.assertTrue(result["entryInHeader"])
        self.assertTrue(result["showInHeader"])
        self.assertTrue(result["open"])
        self.assertIn(meta["latest"]["notesAnchor"], result["notes"])

    def test_mock_does_not_recreate_entries_deleted_by_actual_header_rebuild(self):
        result, _ = self.run_reminder(rebuild_header=True, legacy_header=True)
        self.assertEqual(result["afterRebuild"], {"entryExists": False, "showExists": False})
        self.assertFalse(result["open"])
        self.assertFalse(result["accessInHeader"])

    def test_suppression_applies_to_current_release_only(self):
        first, meta = self.run_reminder(actions=[{"type": "check", "checked": True}, {"type": "click", "id": "wiki-update-read"}])
        key = "lah-wiki-update:suppressed:" + meta["latest"]["pushSha"]
        self.assertTrue(first["initial"]["open"])
        self.assertEqual(first["storage"][key], "1")
        self.assertFalse(first["open"])
        self.assertEqual(first["focused"], "wiki-update-entry")
        again, _ = self.run_reminder(storage=first["storage"])
        self.assertFalse(again["open"])
        meta["latest"]["pushSha"] = "a" * 40
        later, _ = self.run_reminder(storage=first["storage"], metadata=meta)
        self.assertTrue(later["open"])

    def test_force_show_preserves_suppression_and_checkbox(self):
        _, meta = self.run_reminder()
        key = "lah-wiki-update:suppressed:" + meta["latest"]["pushSha"]
        forced, _ = self.run_reminder(storage={key: "1"}, query="?reminder=show", actions=[{"type": "close"}])
        self.assertTrue(forced["initial"]["open"])
        self.assertTrue(forced["initial"]["checked"])
        self.assertEqual(forced["initial"]["mutations"], [])
        self.assertEqual(forced["storage"], {key: "1"})
        self.assertTrue(all(operation[0] != "remove" for operation in forced["mutations"]))

    def test_same_activity_new_release_reminds_without_new_historical_push(self):
        _, meta = self.run_reminder()
        meta["releaseVersion"] = "wiki-test-1"
        first, _ = self.run_reminder(metadata=meta, actions=[
            {"type": "check", "checked": True}, {"type": "close"},
        ])
        self.assertEqual(first["storage"], {"lah-wiki-update:suppressed:wiki-test-1": "1"})
        again, _ = self.run_reminder(metadata=meta, storage=first["storage"])
        self.assertFalse(again["open"])
        latest_push = meta["latest"]["pushSha"]
        meta["releaseVersion"] = "wiki-test-2"
        next_release, returned_meta = self.run_reminder(metadata=meta, storage=first["storage"])
        self.assertEqual(returned_meta["latest"]["pushSha"], latest_push)
        self.assertTrue(next_release["open"])
        self.assertFalse(next_release["checked"])

    def test_invalid_release_identity_falls_back_to_recorded_push(self):
        _, meta = self.run_reminder()
        key = "lah-wiki-update:suppressed:" + meta["latest"]["pushSha"]
        for value in ("", " ", "../invalid", 42):
            with self.subTest(releaseVersion=value):
                meta["releaseVersion"] = value
                result, _ = self.run_reminder(metadata=meta, storage={key: "1"})
                self.assertFalse(result["open"])

    def test_manual_entry_can_explicitly_restore_reminders(self):
        _, meta = self.run_reminder()
        key = "lah-wiki-update:suppressed:" + meta["latest"]["pushSha"]
        result, _ = self.run_reminder(storage={key: "1"}, actions=[
            {"type": "click", "id": "wiki-update-show"},
            {"type": "check", "checked": False}, {"type": "close"},
        ])
        self.assertFalse(result["initial"]["open"])
        self.assertNotIn(key, result["storage"])
        self.assertEqual(result["focused"], "wiki-update-entry")

    def test_notes_link_opens_the_cumulative_activity_page_and_closes_dialog(self):
        result, meta = self.run_reminder(actions=[{"type": "click", "id": "wiki-update-notes"}])
        self.assertEqual(result["notes"], "更新笔记/" + meta["latest"]["notesPath"] + "#" + meta["latest"]["notesAnchor"])
        self.assertEqual(result["title"], meta["activityName"])
        self.assertFalse(result["open"])

    def test_unavailable_storage_keeps_reminder_usable(self):
        result, _ = self.run_reminder(blocked=True)
        self.assertTrue(result["open"])
        self.assertTrue(result["disabled"])
        self.assertIn("无法保存", result["state"])


if __name__ == "__main__":
    unittest.main()
