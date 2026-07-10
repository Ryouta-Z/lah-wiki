"""构建角色主映射表: 代号 -> {中文名, 日文名, 图片bundle}。

数据来源:
- 官方中文站 /cn/character/{code} 提供 代号->中文名/日文名
- CDN catalog 提供 代号->图片bundle 文件名
输出: data/char_map.json
用法: uv run python scripts/build_char_map.py
"""
import html as html_lib
import json
import re
import time
from pathlib import Path

import httpx

LIST_URL = "https://live-a-hero.jp/cn/character_list"
DETAIL_URL = "https://live-a-hero.jp/cn/character/{}"
CATALOG = Path(__file__).parent.parent / "data" / "cache" / "catalog_lah.json"
OUT = Path(__file__).parent.parent / "data" / "char_map.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get(url: str) -> str:
    for _ in range(3):
        try:
            r = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
            if r.status_code == 200:
                return r.text
        except httpx.HTTPError:
            time.sleep(1)
    return ""


def clean(s: str) -> str:
    s = html_lib.unescape(s)
    s = re.sub(r"[⇌↔←→⇔\u2000-\u206f]", "", s)
    return s.strip()


def list_codes() -> list[str]:
    html = get(LIST_URL)
    codes, seen = re.findall(r"/cn/character/([A-Za-z0-9_-]+)", html), []
    for c in codes:
        if c not in seen:
            seen.append(c)
    return seen


def names(code: str):
    html = get(DETAIL_URL.format(code))
    if not html:
        return None, None
    m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
    jp = re.search(r"<title>(.*?)[｜|]", html)
    if not m:
        return None, None
    cn = clean(re.sub(r"CV[:：].*", "", re.sub(r"<[^>]+>", "", m.group(1))))
    jpn = clean(jp.group(1)) if jp else ""
    return (cn or None), (jpn or None)


def load_bundle_index() -> dict:
    """code -> assets_all bundle 文件名。"""
    d = json.load(open(CATALOG, encoding="utf-8"))
    ids = [x.split("/")[-1] for x in d.get("m_InternalIds", []) if isinstance(x, str)]
    idx = {}
    for b in ids:
        m = re.match(r"^([a-z0-9]+)_assets_all_[0-9a-f]{32}\.bundle$", b)
        if m:
            idx[m.group(1)] = b
    return idx


def main():
    codes = list_codes()
    bundles = load_bundle_index()
    print(f"角色代号 {len(codes)}, bundle索引 {len(bundles)}")

    result = {}
    for i, code in enumerate(codes, 1):
        cn, jp = names(code)
        entry = {"cn": cn, "jp": jp, "bundle": bundles.get(code.lower())}
        result[code] = entry
        mark = "✓" if entry["bundle"] else "·"
        print(f"[{i}/{len(codes)}] {mark} {code}: {cn} / {jp}")
        time.sleep(0.3)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=True)
    have_bundle = sum(1 for v in result.values() if v["bundle"])
    print(f"完成: {len(result)} 角色, 其中 {have_bundle} 个有图片bundle -> {OUT}")


if __name__ == "__main__":
    main()
