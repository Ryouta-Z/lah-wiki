"""Build the offline ZIP and compressed, per-file GitHub release assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import zipfile
from pathlib import Path

try:
    from scripts.build_vercel_readonly import _referenced_avatar_filenames, validate_deployment_package
except ModuleNotFoundError:
    from build_vercel_readonly import _referenced_avatar_filenames, validate_deployment_package

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPOSITORY = "Ryouta-Z/lah-wiki"


def build_portable_wiki(
    output: Path,
    version: str,
    repository: str = DEFAULT_REPOSITORY,
    *,
    catalog_path: Path = ROOT / "data/quickref_catalog.json",
    site_path: Path = ROOT / "quickref/index.html",
    icon_dir: Path = ROOT / "data/images/icon",
    ui_dir: Path = ROOT / "quickref/assets/official-ui",
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version):
        raise ValueError("版本名只能包含字母、数字、点、下划线及短横线")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("仓库必须为 owner/repo")
    if output.exists():
        raise ValueError("输出目录已存在，请使用新的版本目录")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    html = site_path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^    const catalog = (.*);$", html)
    if not match or json.loads(match[1]) != catalog:
        raise ValueError("首页与目录数据不一致，请先重建 Wiki")

    # Preserve the current query interface, removing only owner-only controls.
    html = "\n".join(line for line in html.splitlines() if "tagSettings" not in line and ".tag-settings-close" not in line)
    html = re.sub(r'<nav class="wiki-navigation"[^>]*>.*?</nav>', "", html)
    html, avatars_changed = re.subn(r'(?m)^    const avatarUrlPrefix = .*;$', '    const avatarUrlPrefix = "assets/images/icon";', html)
    html, ui_changed = re.subn(r'(?m)^    const localOfficialAssetPrefix = .*;$', '    const localOfficialAssetPrefix = "assets/official-ui";', html)
    if avatars_changed != 1 or ui_changed != 1:
        raise ValueError("无法识别首页图片路径")
    files: dict[str, bytes] = {"index.html": html.encode("utf-8")}
    for filename in sorted(_referenced_avatar_filenames(catalog)):
        if Path(filename).name != filename or "\\" in filename:
            raise ValueError("头像文件名包含路径")
        files[f"assets/images/icon/{filename}"] = (icon_dir / filename).read_bytes()
    if not ui_dir.is_dir():
        raise ValueError("缺少正式 UI 图片目录")
    for path in sorted(ui_dir.glob("*.png")):
        files[f"assets/official-ui/{path.name}"] = path.read_bytes()
    files["update-wiki.ps1"] = (ROOT / "scripts/portable/update-wiki.ps1").read_text(encoding="utf-8-sig").encode("utf-8-sig")
    files["install-wiki.ps1"] = (ROOT / "scripts/portable/install-wiki.ps1").read_text(encoding="utf-8-sig").encode("utf-8-sig")
    files["下载Wiki.cmd"] = ('@echo off\r\nchcp 65001 >nul\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-wiki.ps1"\r\nif errorlevel 1 pause\r\n').encode("utf-8")
    files["打开Wiki.cmd"] = b'@echo off\r\nstart "" "%~dp0index.html"\r\n'
    files["更新Wiki.cmd"] = (
        '@echo off\r\nchcp 65001 >nul\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-wiki.ps1"\r\n'
        'if errorlevel 1 echo 更新未完成。请检查网络后重试，原 Wiki 仍可使用。\r\npause\r\n'
    ).encode("utf-8")
    files["使用说明.txt"] = (
        "Live A Hero 便携 Wiki\r\n\r\n"
        "解压整个压缩包后，双击「打开Wiki.cmd」或 index.html 即可离线查询。\r\n"
        "双击「更新Wiki.cmd」检查更新，只下载新增或变更的文件。更新后刷新浏览器。\r\n"
        "更新需要联网访问 GitHub；无需安装 Python、Git 或其他开发工具。\r\n"
        "下载或校验失败不会替换现有内容；意外中断时再次运行更新器可恢复。\r\n"
        "请保留整个文件夹，不要单独移动首页。勿在更新过程中移动文件夹或关闭窗口。\r\n"
        "仅包含角色、技能、标签及头像；签名、收藏卡和立绘等解包素材暂不提供。\r\n"
        "普通查询包不包含标签管理、原始资源包或机器人配置。\r\n"
    ).encode("utf-8-sig")

    package, release = output / "wiki", output / "release"
    package.mkdir(parents=True)
    release.mkdir()
    base_url = f"https://github.com/{repository}/releases/download/{version}/"
    entries = []
    for name, content in sorted(files.items()):
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        blob = gzip.compress(content, compresslevel=9, mtime=0)
        asset_name = f"blob-{digest}.gz"
        (release / asset_name).write_bytes(blob)
        entries.append({"path": name, "sha256": digest, "size": len(content), "downloadSize": len(blob), "url": base_url + asset_name})
    manifest = {"schemaVersion": 1, "version": version, "files": entries}
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    (package / ".wiki-state.json").write_bytes(manifest_bytes)
    (package / ".wiki-channel.json").write_text(json.dumps({"repository": repository, "manifestUrl": f"https://github.com/{repository}/releases/latest/download/wiki-manifest.json"}), encoding="utf-8")
    (release / "wiki-manifest.json").write_bytes(manifest_bytes)
    validate_deployment_package(package, catalog)
    if len(list(release.iterdir())) + 2 > 1000:
        raise ValueError("发布文件超出 GitHub 单版本的 1000 个附件限制")
    zip_path = release / "Live-A-Hero-Wiki.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, "Live-A-Hero-Wiki/" + path.relative_to(package).as_posix())
    setup_path = release / "Live-A-Hero-Wiki-Setup.zip"
    with zipfile.ZipFile(setup_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ("update-wiki.ps1", "install-wiki.ps1", "下载Wiki.cmd", ".wiki-channel.json"):
            archive.write(package / name, "Live-A-Hero-Wiki/" + name)
        archive.writestr("Live-A-Hero-Wiki/.wiki-state.json", json.dumps({"schemaVersion": 1, "version": "not-installed", "files": []}))
        archive.writestr("Live-A-Hero-Wiki/使用说明.txt", "解压整个文件夹，双击「下载Wiki.cmd」，选择 Wiki 后开始下载。\r\n下载完成后可离线打开；签名、收藏卡、立绘等补充素材暂不提供。\r\n".encode("utf-8-sig"))
    return {"version": version, "files": len(entries), "zip": str(zip_path), "zipBytes": zip_path.stat().st_size, "setupZip": str(setup_path), "setupBytes": setup_path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description="构建便携 Wiki 和增量更新发布文件")
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_portable_wiki(args.output, args.version, args.repository), ensure_ascii=False))


if __name__ == "__main__":
    main()
