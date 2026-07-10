"""批量下载角色图片: 从 CDN 拉取各角色 bundle, 解出头像和立绘 PNG。

依赖 data/char_map.json (由 build_char_map.py 生成)。
输出:
  data/images/icon/{code}.png     头像 (优先 h01)
  data/images/portrait/{code}.png  立绘 (spine_*)
用法: uv run python scripts/fetch_images.py
"""
import json
import time
from pathlib import Path

import httpx
import UnityPy

ROOT = Path(__file__).parent.parent
CHAR_MAP = ROOT / "data" / "char_map.json"
CDN = "https://d1itvxfdul6wxg.cloudfront.net/4.13.2/Assetbundle/Android/"
ICON_DIR = ROOT / "data" / "images" / "icon"
PORTRAIT_DIR = ROOT / "data" / "images" / "portrait"
UA = {"User-Agent": "UnityPlayer"}


def download(fn: str) -> bytes | None:
    for _ in range(3):
        try:
            r = httpx.get(CDN + fn, headers=UA, timeout=90)
            if r.status_code == 200:
                return r.content
        except httpx.HTTPError:
            time.sleep(1)
    return None


def pick_textures(env, code: str):
    """返回 (icon_img, portrait_img)。优先 h01 头像和 spine 立绘。"""
    icons, portraits = {}, {}
    for o in env.objects:
        if o.type.name != "Texture2D":
            continue
        d = o.read()
        nm = getattr(d, "m_Name", "")
        low = nm.lower()
        if low.startswith("icon_"):
            icons[low] = d.image
        elif low.startswith("spine_") or "_spine" in low:
            portraits[low] = d.image
    icon = None
    for key in sorted(icons):
        if "h01" in key and "skin" not in key:
            icon = icons[key]
            break
    if icon is None and icons:
        icon = icons[sorted(icons)[0]]
    portrait = portraits[sorted(portraits)[0]] if portraits else None
    return icon, portrait


def main():
    char_map = json.load(open(CHAR_MAP, encoding="utf-8"))
    targets = {c: v for c, v in char_map.items() if v.get("bundle")}
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"待下载 {len(targets)} 个角色")

    ok_icon = ok_portrait = 0
    for i, (code, v) in enumerate(targets.items(), 1):
        icon_path = ICON_DIR / f"{code}.png"
        if icon_path.exists():
            ok_icon += 1
            print(f"[{i}/{len(targets)}] {code}: 已存在, 跳过")
            continue
        data = download(v["bundle"])
        if not data:
            print(f"[{i}/{len(targets)}] {code}: 下载失败")
            continue
        try:
            env = UnityPy.load(data)
            icon, portrait = pick_textures(env, code)
            if icon:
                icon.save(icon_path)
                ok_icon += 1
            if portrait:
                portrait.save(PORTRAIT_DIR / f"{code}.png")
                ok_portrait += 1
            print(f"[{i}/{len(targets)}] {code} ({v['cn']}): icon={'✓' if icon else '×'} portrait={'✓' if portrait else '×'}")
        except Exception as e:
            print(f"[{i}/{len(targets)}] {code}: 解包失败 {type(e).__name__}")
        time.sleep(0.2)

    print(f"完成: 头像 {ok_icon}, 立绘 {ok_portrait}")


if __name__ == "__main__":
    main()
