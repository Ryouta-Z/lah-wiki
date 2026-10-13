import gzip
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_portable_wiki import ROOT, build_portable_wiki
from scripts.lah_quickref import render_static_html


class PortableBuildTest(unittest.TestCase):
    def test_zip_preserves_interface_and_includes_only_public_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = {"metadata": {}, "cards": [], "heroTags": [], "assistantTags": [], "statusTerms": [], "skills": [], "skillUpgrades": []}
            (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            html = render_static_html(catalog).replace(
                "</header>", '<nav class="wiki-navigation"><a href="collection-cards/index.html">收藏卡</a></nav></header>'
            )
            (root / "index.html").write_text(html.replace("</body>", '<div id="custom-query-interface">custom</div></body>'), encoding="utf-8")
            ui = root / "ui"
            ui.mkdir()
            (ui / "element-fire.png").write_bytes(b"ui image")
            collection = root / "collection"
            (collection / "assets").mkdir(parents=True)
            (collection / "index.html").write_text('<img src="assets/cover.png">', encoding="utf-8")
            (collection / "assets/cover.png").write_bytes(b"cover")
            result = build_portable_wiki(root / "output", "wiki-test", catalog_path=root / "catalog.json", site_path=root / "index.html", ui_dir=ui)
            page = (root / "output/wiki/index.html").read_text(encoding="utf-8")
            self.assertIn('id="custom-query-interface"', page)
            self.assertIn('"assets/official-ui"', page)
            self.assertNotIn("tagSettings", page)
            self.assertNotIn("127.0.0.1", page)
            embedded_meta = re.search(r'<script type="application/json" id="wiki-update-meta">(.*?)</script>', page, re.S)
            self.assertIsNotNone(embedded_meta)
            self.assertEqual(json.loads(embedded_meta[1])["releaseVersion"], "wiki-test")
            manifest = json.loads((root / "output/release/wiki-manifest.json").read_text(encoding="utf-8"))
            notes_files = {"更新笔记/20261008-heroes-blues.html", "更新笔记/style.css", "更新笔记/update-meta.json"}
            template_files = {"更新笔记/reminder.html", "更新笔记/reminder.css", "更新笔记/reminder.js"}
            manifest_paths = {entry["path"] for entry in manifest["files"]}
            self.assertTrue(notes_files <= manifest_paths)
            self.assertTrue(template_files.isdisjoint(manifest_paths))
            notes_page = root / "output/wiki/更新笔记/20261008-heroes-blues.html"
            notes_html = notes_page.read_text(encoding="utf-8")
            self.assertIn('id="update-4bdfb98"', notes_html)
            self.assertIn('id="update-6e9febd"', notes_html)
            note_images = re.findall(r'<img[^>]+src="([^"]+)"', notes_html)
            self.assertEqual(len(note_images), 5)
            for reference in note_images:
                self.assertTrue(reference.startswith("../assets/images/icon/"), reference)
                self.assertTrue((notes_page.parent / reference).is_file(), reference)
            for entry in manifest["files"]:
                blob = root / "output/release" / ("blob-" + entry["sha256"] + ".gz")
                content = gzip.decompress(blob.read_bytes())
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
                self.assertEqual(len(content), entry["size"])
            with zipfile.ZipFile(result["zip"]) as archive:
                self.assertIn("Live-A-Hero-Wiki/更新Wiki.cmd", archive.namelist())
                self.assertTrue({"Live-A-Hero-Wiki/" + name for name in notes_files} <= set(archive.namelist()))
                self.assertTrue({"Live-A-Hero-Wiki/" + name for name in template_files}.isdisjoint(archive.namelist()))
                self.assertFalse(any("collection-cards" in name for name in archive.namelist()))
                self.assertTrue(all(".env" not in name for name in archive.namelist()))
                for name in archive.namelist():
                    if Path(name).suffix in {".html", ".css", ".js", ".json"}:
                        content = archive.read(name).decode("utf-8")
                        self.assertNotIn("__UPDATE_NOTES_BASE__", content, name)
                        self.assertNotIn("__WIKI_UPDATE_META_JSON__", content, name)
            self.assertNotIn("collection-cards/index.html", page)
            with zipfile.ZipFile(result["setupZip"]) as archive:
                self.assertIn("Live-A-Hero-Wiki/下载Wiki.cmd", archive.namelist())
                self.assertFalse(any(name.endswith("index.html") or name.endswith(".png") for name in archive.namelist()))
            with zipfile.ZipFile(result["updaterZip"]) as archive:
                self.assertEqual(set(archive.namelist()), {"update-wiki.ps1", "更新器升级说明.txt"})
                self.assertEqual(archive.read("update-wiki.ps1").decode("utf-8-sig"), (ROOT / "scripts/portable/update-wiki.ps1").read_text(encoding="utf-8-sig"))
                instructions = archive.read("更新器升级说明.txt").decode("utf-8-sig")
                self.assertIn("update-wiki.ps1", instructions)
                self.assertIn(".wiki-state.json", instructions)
            with self.assertRaisesRegex(ValueError, "已存在"):
                build_portable_wiki(root / "output", "wiki-test")

    def test_rejects_stale_embedded_catalog_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.json").write_text('{"cards": []}', encoding="utf-8")
            (root / "index.html").write_text('    const catalog = {};', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "不一致"):
                build_portable_wiki(root / "output", "wiki-test", catalog_path=root / "catalog.json", site_path=root / "index.html")
            self.assertFalse((root / "output").exists())


@unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell 5.1 required")
class PortableUpdaterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.wiki = self.root / "中文 文件夹" / "Wiki"
        self.wiki.mkdir(parents=True)
        self.remote = self.root / "remote"
        self.remote.mkdir()
        self.updater = (ROOT / "scripts/portable/update-wiki.ps1").read_bytes()
        self.old_files = {"index.html": b"old page", "update-wiki.ps1": self.updater, "assets/images/icon/unchanged.png": b"same image", "assets/images/icon/removed.png": b"old image"}
        self.old_manifest = self.make_manifest("wiki-old", self.old_files)
        for name, content in self.old_files.items():
            path = self.wiki / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.write_json(self.wiki / ".wiki-state.json", self.old_manifest)
        self.write_json(self.wiki / ".wiki-channel.json", {"repository": "Ryouta-Z/lah-wiki", "manifestUrl": "https://github.com/Ryouta-Z/lah-wiki/releases/latest/download/wiki-manifest.json"})
        (self.wiki / "my-notes.txt").write_bytes(b"user file")

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def make_manifest(self, version, files):
        entries = []
        for name, content in sorted(files.items()):
            digest = hashlib.sha256(content).hexdigest()
            blob = gzip.compress(content, mtime=0)
            asset = "blob-" + digest + ".gz"
            (self.remote / asset).write_bytes(blob)
            entries.append({"path": name, "sha256": digest, "size": len(content), "downloadSize": len(blob), "url": f"https://github.com/Ryouta-Z/lah-wiki/releases/download/{version}/{asset}"})
        with zipfile.ZipFile(self.remote / "Live-A-Hero-Wiki.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr("Live-A-Hero-Wiki/" + name, content)
        return {"schemaVersion": 1, "version": version, "files": entries}

    def run_update(self, manifest, extra=""):
        self.write_json(self.remote / "wiki-manifest.json", manifest)
        quote = lambda p: "'" + str(p).replace("'", "''") + "'"
        script = f"""
$ErrorActionPreference = 'Stop'
. {quote(self.wiki / 'update-wiki.ps1')} -LibraryOnly
$script:requests = @()
function Download-WikiFile([string]$Url, [string]$Destination) {{
    $script:requests += $Url
    $name = $Url.Substring($Url.LastIndexOf('/') + 1)
    [IO.File]::Copy((Join-Path {quote(self.remote)} $name), $Destination, $true)
}}
{extra}
try {{ $result = Invoke-WikiUpdate {quote(self.wiki)}; $out = @{{ok=$true; result=$result}} }}
catch {{ $out = @{{ok=$false; error=$_.Exception.Message}} }}
$out.requests = @($script:requests)
$out | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath {quote(self.root / 'result.json')} -Encoding UTF8
"""
        script_path = self.root / "run.ps1"
        script_path.write_text(script, encoding="utf-8-sig")
        process = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)], capture_output=True, timeout=45)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        return json.loads((self.root / "result.json").read_text(encoding="utf-8-sig"))

    def test_skips_intermediate_versions_downloads_only_changes_and_repeat_is_noop(self):
        files = {**self.old_files, "index.html": b"latest page", "assets/images/icon/new.png": b"new image"}
        del files["assets/images/icon/removed.png"]
        manifest = self.make_manifest("wiki-latest", files)
        result = self.run_update(manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], 2)
        self.assertEqual(len(result["requests"]), 3)  # Manifest plus two changed files.
        self.assertFalse((self.wiki / "assets/images/icon/removed.png").exists())
        self.assertEqual((self.wiki / "my-notes.txt").read_bytes(), b"user file")
        again = self.run_update(manifest)
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["result"]["downloaded"], 0)
        self.assertEqual(len(again["requests"]), 1)

    def test_downloads_current_and_historical_release_notes_with_styles_and_metadata(self):
        notes = {
            "更新笔记/202609-old-event.html": b"previous activity notes",
            "更新笔记/20261008-heroes-blues.html": b"current activity notes",
            "更新笔记/style.css": b"notes styles",
            "更新笔记/reminder.js": b"reminder script",
            "更新笔记/update-meta.json": b'{"activityId":"20261008-heroes-blues"}',
        }
        manifest = self.make_manifest("wiki-notes-new", {**self.old_files, **notes, "index.html": b"new page with notes"})
        result = self.run_update(manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], len(notes) + 1)
        for name, content in notes.items():
            self.assertEqual((self.wiki / name).read_bytes(), content)
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"new page with notes")
        self.assertEqual((self.wiki / "my-notes.txt").read_bytes(), b"user file")
        self.assertEqual(json.loads((self.wiki / ".wiki-state.json").read_text(encoding="utf-8")), manifest)

    def test_skipping_versions_keeps_all_prior_activity_notes(self):
        first_files = {
            **self.old_files,
            "更新笔记/202609-old-event.html": b"first activity notes",
            "更新笔记/style.css": b"old notes styles",
        }
        first = self.make_manifest("wiki-notes-first", first_files)
        self.assertTrue(self.run_update(first)["ok"])
        skipped_files = {
            **first_files,
            "index.html": b"skipped page",
            "更新笔记/20261008-heroes-blues.html": b"second activity notes",
        }
        self.make_manifest("wiki-notes-skipped", skipped_files)
        latest_files = {
            **skipped_files,
            "index.html": b"latest page",
            "更新笔记/202610-next-event.html": b"latest activity notes",
            "更新笔记/style.css": b"latest notes styles",
        }
        latest = self.make_manifest("wiki-notes-latest", latest_files)
        result = self.run_update(latest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], 4)
        self.assertEqual(result["result"]["removed"], 0)
        for name, content in latest_files.items():
            self.assertEqual((self.wiki / name).read_bytes(), content)
        self.assertFalse(any("/wiki-notes-skipped/" in request for request in result["requests"]))
        self.assertEqual(json.loads((self.wiki / ".wiki-state.json").read_text(encoding="utf-8")), latest)

    def test_corrupt_release_notes_keep_old_homepage_notes_styles_and_state(self):
        old_files = {
            **self.old_files,
            "更新笔记/20261008-heroes-blues.html": b"old activity notes",
            "更新笔记/style.css": b"old notes styles",
        }
        old_manifest = self.make_manifest("wiki-notes-old", old_files)
        self.assertTrue(self.run_update(old_manifest)["ok"])
        old_state = (self.wiki / ".wiki-state.json").read_bytes()
        new_manifest = self.make_manifest("wiki-notes-new", {
            **old_files,
            "index.html": b"new page",
            "更新笔记/20261008-heroes-blues.html": b"new activity notes",
            "更新笔记/style.css": b"new notes styles",
            "更新笔记/202610-next-event.html": b"new historical page",
        })
        entry = next(e for e in new_manifest["files"] if e["path"] == "更新笔记/20261008-heroes-blues.html")
        blob_path = self.remote / entry["url"].split("/")[-1]
        corrupt_notes = b"bad activity notes"
        self.assertEqual(len(corrupt_notes), entry["size"])
        blob_path.write_bytes(gzip.compress(corrupt_notes, mtime=0))
        entry["downloadSize"] = blob_path.stat().st_size
        result = self.run_update(new_manifest)
        self.assertFalse(result["ok"])
        self.assertIn("校验失败", result["error"])
        self.assertIn("更新笔记/20261008-heroes-blues.html", result["error"])
        for name, content in old_files.items():
            self.assertEqual((self.wiki / name).read_bytes(), content)
        self.assertEqual((self.wiki / ".wiki-state.json").read_bytes(), old_state)
        self.assertFalse((self.wiki / "更新笔记/202610-next-event.html").exists())
        self.assertFalse((self.wiki / ".wiki-update").exists())

    def test_frozen_legacy_updater_rejects_notes_then_script_only_upgrade_can_skip_versions(self):
        frozen_updater = subprocess.check_output([
            "git", "show", "4bdfb983b4183db4560525a88c1f21584ee4f49d:scripts/portable/update-wiki.ps1"
        ], cwd=ROOT)
        self.assertNotEqual(frozen_updater, self.updater)
        legacy_files = {**self.old_files, "update-wiki.ps1": frozen_updater}
        legacy_manifest = self.make_manifest("wiki-legacy", legacy_files)
        (self.wiki / "update-wiki.ps1").write_bytes(frozen_updater)
        self.write_json(self.wiki / ".wiki-state.json", legacy_manifest)
        legacy_state = (self.wiki / ".wiki-state.json").read_bytes()
        skipped_files = {
            **legacy_files,
            "update-wiki.ps1": self.updater,
            "index.html": b"skipped page with notes",
            "更新笔记/202609-old-event.html": b"historical notes",
            "更新笔记/style.css": b"notes styles",
        }
        self.make_manifest("wiki-legacy-skipped", skipped_files)
        latest_files = {
            **skipped_files,
            "index.html": b"latest page with cumulative notes",
            "更新笔记/20261008-heroes-blues.html": b"latest activity notes",
        }
        manifest = self.make_manifest("wiki-legacy-latest", latest_files)
        rejected = self.run_update(manifest)
        self.assertFalse(rejected["ok"])
        self.assertIn("更新文件路径不合法：更新笔记/", rejected["error"])
        self.assertEqual(len(rejected["requests"]), 1)
        self.assertEqual((self.wiki / "update-wiki.ps1").read_bytes(), frozen_updater)
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")
        self.assertEqual((self.wiki / ".wiki-state.json").read_bytes(), legacy_state)
        self.assertFalse((self.wiki / "更新笔记").exists())
        self.assertFalse((self.wiki / ".wiki-update").exists())

        # Upgrade only the updater file; the homepage and version state stay old until it succeeds.
        (self.wiki / "update-wiki.ps1").write_bytes(self.updater)
        self.assertEqual((self.wiki / ".wiki-state.json").read_bytes(), legacy_state)
        result = self.run_update(manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], 4)
        for name, content in latest_files.items():
            self.assertEqual((self.wiki / name).read_bytes(), content)
        self.assertFalse(any("/wiki-legacy-skipped/" in request for request in result["requests"]))
        self.assertEqual((self.wiki / "my-notes.txt").read_bytes(), b"user file")
        self.assertEqual(json.loads((self.wiki / ".wiki-state.json").read_text(encoding="utf-8")), manifest)

    def test_corrupt_download_keeps_all_old_files_and_version(self):
        manifest = self.make_manifest("wiki-new", {**self.old_files, "index.html": b"new page"})
        entry = next(e for e in manifest["files"] if e["path"] == "index.html")
        blob_path = self.remote / entry["url"].split("/")[-1]
        blob_path.write_bytes(gzip.compress(b"wrong page", mtime=0))
        entry["downloadSize"] = blob_path.stat().st_size
        result = self.run_update(manifest)
        self.assertFalse(result["ok"])
        self.assertIn("校验失败", result["error"])
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")
        self.assertEqual(json.loads((self.wiki / ".wiki-state.json").read_text())["version"], "wiki-old")
        self.assertFalse((self.wiki / ".wiki-update").exists())

    def test_write_failure_rolls_back_after_an_earlier_file_was_replaced(self):
        files = {**self.old_files, "index.html": b"new page", "assets/images/icon/new.png": b"new image"}
        manifest = self.make_manifest("wiki-new", files)
        fault = r"""
function Copy-Item {
    param([string]$LiteralPath, [string]$Destination, [switch]$Force)
    if ($LiteralPath -like '*\.wiki-update\new\index.html') { throw 'simulated write failure' }
    Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force
}
"""
        result = self.run_update(manifest, fault)
        self.assertFalse(result["ok"])
        self.assertIn("simulated write failure", result["error"])
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")
        self.assertFalse((self.wiki / "assets/images/icon/new.png").exists())
        self.assertEqual(json.loads((self.wiki / ".wiki-state.json").read_text())["version"], "wiki-old")

    def test_path_escape_is_rejected_before_downloading_assets(self):
        manifest = self.make_manifest("wiki-new", self.old_files)
        bad = dict(manifest["files"][0], path="../outside.png")
        manifest["files"].append(bad)
        result = self.run_update(manifest)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["requests"]), 1)
        self.assertFalse((self.wiki.parent / "outside.png").exists())

    def test_next_run_recovers_an_interrupted_replacement(self):
        transaction = self.wiki / ".wiki-update"
        (transaction / "backup").mkdir(parents=True)
        (transaction / "backup/index.html").write_bytes(b"old page")
        self.write_json(transaction / "previous-state.json", self.old_manifest)
        self.write_json(transaction / "journal.json", {"newStateHash": "0" * 64, "operations": [{"path": "index.html", "existed": True}, {"path": "assets/images/icon/new.png", "existed": False}]})
        (self.wiki / "index.html").write_bytes(b"interrupted new page")
        (self.wiki / "assets/images/icon/new.png").write_bytes(b"partial new image")
        result = self.run_update(self.old_manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], 0)
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")
        self.assertFalse((self.wiki / "assets/images/icon/new.png").exists())

    def test_first_download_uses_one_full_archive_then_incremental_updates(self):
        for name in self.old_files:
            if name != "update-wiki.ps1":
                (self.wiki / name).unlink()
        self.write_json(self.wiki / ".wiki-state.json", {"schemaVersion": 1, "version": "not-installed", "files": []})
        result = self.run_update(self.old_manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["requests"]), 2)
        self.assertTrue(result["requests"][1].endswith("/Live-A-Hero-Wiki.zip"))
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")
        self.assertEqual((self.wiki / "my-notes.txt").read_bytes(), b"user file")
        next_manifest = self.make_manifest("wiki-next", {**self.old_files, "index.html": b"new page"})
        result = self.run_update(next_manifest)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["downloaded"], 1)
        self.assertTrue(result["requests"][1].endswith(".gz"))

    def test_network_failure_keeps_old_wiki(self):
        result = self.run_update(self.old_manifest, "function Download-WikiFile { throw 'simulated offline' }")
        self.assertFalse(result["ok"])
        self.assertIn("simulated offline", result["error"])
        self.assertEqual((self.wiki / "index.html").read_bytes(), b"old page")


if __name__ == "__main__":
    unittest.main()
