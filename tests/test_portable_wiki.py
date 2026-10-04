import gzip
import hashlib
import json
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
            html = render_static_html(catalog, collection_cards_url="collection-cards/index.html")
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
            manifest = json.loads((root / "output/release/wiki-manifest.json").read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                blob = root / "output/release" / ("blob-" + entry["sha256"] + ".gz")
                content = gzip.decompress(blob.read_bytes())
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
                self.assertEqual(len(content), entry["size"])
            with zipfile.ZipFile(result["zip"]) as archive:
                self.assertIn("Live-A-Hero-Wiki/更新Wiki.cmd", archive.namelist())
                self.assertFalse(any("collection-cards" in name for name in archive.namelist()))
                self.assertTrue(all(".env" not in name for name in archive.namelist()))
            self.assertNotIn("collection-cards/index.html", page)
            with zipfile.ZipFile(result["setupZip"]) as archive:
                self.assertIn("Live-A-Hero-Wiki/下载Wiki.cmd", archive.namelist())
                self.assertFalse(any(name.endswith("index.html") or name.endswith(".png") for name in archive.namelist()))
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
