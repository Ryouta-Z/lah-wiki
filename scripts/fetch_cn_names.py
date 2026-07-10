"""从 Live A Hero 官方中文站抓取角色中文名, 生成中文别名表。

数据源: https://live-a-hero.jp/cn/character_list
思路: 列表页拿到所有角色代号 -> 逐个访问详情页提取中文名 -> 与游戏数据日文名对应
输出: 合并进 data/aliases.json
用法: uv run python scripts/fetch_cn_names.py
"""
import html as html_lib
import json
import re
import time
from pathlib import Path

import httpx

LIST_URL = "https://live-a-hero.jp/cn/character_list"
DETAIL_URL = "https://live-a-hero.jp/cn/character/{}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

ALIAS_FILE = Path(__file__).parent.parent / "data" / "aliases.json"


def get(url: str) -> str:
    for _ in range(3):
        try:
            r = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
            if r.status_code == 200:
                return r.text
        except httpx.HTTPError:
            time.sleep(1)
    return ""


def list_codes() -> list[str]:
    html = get(LIST_URL)
    codes = re.findall(r"/cn/character/([A-Za-z0-9_-]+)", html)
    seen = []
    for c in codes:
        if c not in seen:
            seen.append(c)
    return seen


def extract(code: str):
    """返回 (中文名, 日文名) 或 (None, None)。"""
    html = get(DETAIL_URL.format(code))
    if not html:
        return None, None
    m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
    jp_m = re.search(r"<title>(.*?)[｜|]", html)
    if not m:
        return None, None
    cn = re.sub(r"CV[:：].*", "", re.sub(r"<[^>]+>", "", m.group(1)))
    jp = jp_m.group(1) if jp_m else ""
    return (_clean_name(cn) or None), (_clean_name(jp) or None)


def _clean_name(s: str) -> str:
    """解码 HTML 实体, 去掉装饰符号和多余空白。"""
    s = html_lib.unescape(s)
    s = re.sub(r"[⇌↔←→⇔\u2000-\u206f]", "", s)
    return s.strip()


def main():
    codes = list_codes()
    print(f"角色数: {len(codes)}")

    existing = {}
    if ALIAS_FILE.exists():
        with open(ALIAS_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    added = 0
    for i, code in enumerate(codes, 1):
        cn, jp = extract(code)
        if cn and jp:
            if cn not in existing:
                existing[cn] = jp
                added += 1
            print(f"[{i}/{len(codes)}] {code}: {cn} <- {jp}")
        else:
            print(f"[{i}/{len(codes)}] {code}: 跳过(未提取到)")
        time.sleep(0.3)

    with open(ALIAS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"完成: 新增 {added} 条, 共 {len(existing)} 条 -> {ALIAS_FILE}")


if __name__ == "__main__":
    main()
