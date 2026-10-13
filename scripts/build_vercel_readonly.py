"""Build the standalone, read-only static package for Vercel."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.lah_quickref import (
        DEFAULT_CATALOG_PATH,
        DEFAULT_ICON_DIR,
        ROOT,
        render_static_html,
    )
except ModuleNotFoundError:  # Allow `python scripts/build_vercel_readonly.py` from the project root.
    from lah_quickref import (  # type: ignore[no-redef]
        DEFAULT_CATALOG_PATH,
        DEFAULT_ICON_DIR,
        ROOT,
        render_static_html,
    )


DEFAULT_OUTPUT_DIR = ROOT / "vercel-readonly"
BUILD_MARKER = ".lah-vercel-readonly-build"
FORBIDDEN_HTML_PATTERNS = (
    r"(?i)127\.0\.0\.1",
    r"(?i)localhost",
    r"(?i)/api/[^\"']*(tags|cards)",
    r"(?i)(assistant_tag_admin|tag_admin)",
    r"(?i)fastapi",
    r"(?i)uvicorn",
    r"(?i)\bfetch\s*\(",
    r"(?i)\b(onebot_access_token|api[_-]?key|authorization|bearer|cookie|password|secret)\b",
    r"(?i)[a-z]:\\",
)
FORBIDDEN_PART_NAMES = {".env", ".venv", "node_modules", "data", "scripts", "__pycache__"}


def _read_catalog(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _referenced_avatar_filenames(catalog: dict[str, Any]) -> set[str]:
    filenames = set()
    for card in catalog.get("cards", []):
        avatar = card.get("avatar") or {}
        if avatar.get("status") != "available":
            continue
        filename = avatar.get("filename") or f"{avatar.get('code', '')}.png"
        if not avatar.get("code") or not filename:
            raise ValueError(f"头像记录不完整：{card.get('key', '未知卡片')}")
        filenames.add(filename)
    return filenames


def _update_note_files() -> dict[str, bytes]:
    """Ship cumulative activity pages, not the embedded reminder's source templates."""
    files = {}
    for path in sorted((ROOT / "quickref" / "更新笔记").iterdir()):
        if path.name in {"reminder.html", "reminder.css", "reminder.js"}:
            continue
        if path.is_symlink() or not path.is_file() or not re.fullmatch(
            r"(?:[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:html|css)|update-meta\.json)", path.name
        ):
            raise ValueError(f"不支持的更新笔记文件：{path.name}")
        content = path.read_bytes()
        if path.suffix == ".html":
            content = content.decode("utf-8").replace(
                "../../data/images/icon/", "../assets/images/icon/"
            ).encode("utf-8")
        files[f"更新笔记/{path.name}"] = content
    return files


def _note_avatar_filenames(files: dict[str, bytes]) -> set[str]:
    return {
        filename
        for name, content in files.items() if name.endswith(".html")
        for filename in re.findall(r"\.\./assets/images/icon/([A-Za-z0-9_.-]+\.(?:png|gif))", content.decode("utf-8"))
    }


def validate_deployment_package(
    output_dir: Path,
    catalog: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Reject local-only code, credentials, and missing public assets."""
    output_dir = output_dir.resolve()
    index_path = output_dir / "index.html"
    if not index_path.is_file():
        raise ValueError(f"缺少公开首页：{index_path}")

    for path in output_dir.rglob("*"):
        relative_parts = path.relative_to(output_dir).parts
        if any(part.lower() in FORBIDDEN_PART_NAMES for part in relative_parts):
            raise ValueError(f"部署目录包含禁止内容：{path.relative_to(output_dir)}")
        if path.is_file() and (path.suffix.lower() in {".log", ".py", ".pyc", ".sqlite", ".db"}):
            raise ValueError(f"部署目录包含禁止文件：{path.relative_to(output_dir)}")

    html = index_path.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_HTML_PATTERNS:
        if re.search(pattern, html):
            raise ValueError(f"公开首页包含禁止内容：{pattern}")
    if 'id="tagSettings"' in html or 'id="tagSettingsDetail"' in html:
        raise ValueError("公开首页仍包含标签管理入口")
    if "const catalog =" not in html or 'id="hero-tags"' not in html or 'id="assistant-tags"' not in html or "avatarMarkup" not in html:
        raise ValueError("公开首页缺少查询、标签筛选或头像展示功能")

    expected_filenames = _referenced_avatar_filenames(catalog) if catalog is not None else set()
    asset_dir = output_dir / "assets" / "images" / "icon"
    missing = [filename for filename in sorted(expected_filenames) if not (asset_dir / filename).is_file()]
    if missing:
        raise ValueError(f"缺少公开头像：{', '.join(missing[:5])}")
    if 'id="wiki-update-meta"' in html:
        metadata = json.loads(re.search(r'<script type="application/json" id="wiki-update-meta">(.*?)</script>', html, re.S)[1])
        latest = metadata["latest"]
        notes_dir = output_dir / "更新笔记"
        latest_page = notes_dir / latest["notesPath"]
        if not latest_page.is_file() or f'id="{latest["notesAnchor"]}"' not in latest_page.read_text(encoding="utf-8"):
            raise ValueError("最新更新笔记页面或定位入口缺失")
        note_files = {path.name: path.read_bytes() for path in notes_dir.glob("*.html")}
        for name, content in note_files.items():
            page = content.decode("utf-8")
            if "../../data/" in page or "prototype" in page or re.search(r"(?:src|href)=[\"'](?:https?://|file:)", page):
                raise ValueError(f"更新笔记包含非离线资源：{name}")
            for reference in re.findall(r'(?:src|href)="([^"?#]+)', page):
                target = (notes_dir / reference).resolve()
                if not target.is_relative_to(output_dir) or not target.is_file():
                    raise ValueError(f"更新笔记资源缺失或越界：{name} → {reference}")
    return {"avatars": len(expected_filenames), "files": sum(path.is_file() for path in output_dir.rglob("*"))}


def build_vercel_readonly(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    icon_dir: Path = DEFAULT_ICON_DIR,
) -> dict[str, int]:
    """Create an upload-ready static package without changing source data."""
    catalog = _read_catalog(catalog_path)
    filenames = _referenced_avatar_filenames(catalog)
    output_dir = output_dir.resolve()
    if output_dir == ROOT.resolve():
        raise ValueError("拒绝将部署包输出到项目根目录")
    if output_dir.exists() and not (output_dir / BUILD_MARKER).is_file():
        raise ValueError(f"拒绝覆盖非本脚本生成的目录：{output_dir}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="lah-vercel-readonly-", dir=output_dir.parent))
    try:
        (staging_dir / BUILD_MARKER).write_text("Generated by scripts/build_vercel_readonly.py\n", encoding="utf-8")
        (staging_dir / "index.html").write_text(
            render_static_html(
                catalog,
                "assets/images/icon",
                use_official_card_layout=True,
                include_tag_settings=False,
            ),
            encoding="utf-8",
        )
        destination_icons = staging_dir / "assets" / "images" / "icon"
        destination_icons.mkdir(parents=True)
        for filename in sorted(filenames):
            source = icon_dir / filename
            if not source.is_file():
                raise ValueError(f"源头像不存在：{source}")
            shutil.copy2(source, destination_icons / filename)

        note_files = _update_note_files()
        for name, content in note_files.items():
            target = staging_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for filename in sorted(_note_avatar_filenames(note_files) - filenames):
            shutil.copy2(ROOT / "data/images/icon" / filename, destination_icons / filename)

        summary = validate_deployment_package(staging_dir, catalog)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging_dir.replace(output_dir)
        return summary
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 Vercel 只读静态查询包")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--icons", type=Path, default=DEFAULT_ICON_DIR)
    args = parser.parse_args()
    summary = build_vercel_readonly(args.output, args.catalog, args.icons)
    print(f"已生成 Vercel 只读包：{args.output}（{summary['avatars']} 个头像，{summary['files']} 个文件）")


if __name__ == "__main__":
    main()
