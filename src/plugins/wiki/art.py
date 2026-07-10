"""按需立绘查询: /立绘 角色名 -> 从社群仓库拉取完整立绘并发送。

数据源: https://github.com/liveahero-community/assets (社群资料站, 开源)
立绘命名: build/illustrations/{code}_h01.png
"""
import json
import time
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
CHAR_MAP_FILE = DATA_DIR / "char_map.json"
CACHE_DIR = DATA_DIR / "cache" / "illust"
ASSETS_RAW = "https://raw.githubusercontent.com/liveahero-community/assets/main/build/illustrations/"
UA = {"User-Agent": "Mozilla/5.0"}


def _load_char_map() -> dict:
    if not CHAR_MAP_FILE.exists():
        return {}
    with open(CHAR_MAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_code(name: str) -> str | None:
    """按中文名/日文名找角色代号。"""
    cmap = _load_char_map()
    if name in cmap:
        return name
    for code, v in cmap.items():
        if name in (v.get("cn"), v.get("jp")):
            return code
    for code, v in cmap.items():
        cn, jp = v.get("cn") or "", v.get("jp") or ""
        if name and (name in cn or name in jp):
            return code
    return None


def fetch_illust(code: str) -> Path | None:
    """下载立绘(优先 h01), 带本地缓存和重试。返回本地路径或 None。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for variant in ("h01", "s01"):
        cache = CACHE_DIR / f"{code}_{variant}.png"
        if cache.exists():
            return cache
        data = _download(f"{code}_{variant}.png")
        if data:
            cache.write_bytes(data)
            return cache
    return None


def _download(fn: str) -> bytes | None:
    for _ in range(4):
        try:
            r = httpx.get(ASSETS_RAW + fn, headers=UA, timeout=60)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return None
        except httpx.HTTPError:
            time.sleep(1.5)
    return None
