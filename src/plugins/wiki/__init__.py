import json
from pathlib import Path
from difflib import get_close_matches

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from .online import search_online
from .art import resolve_code, fetch_illust

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_FILES = ["wiki_local.json", "lah_data.json"]
ALIAS_FILE = DATA_DIR / "aliases.json"
CHAR_MAP_FILE = DATA_DIR / "char_map.json"
ICON_DIR = DATA_DIR / "images" / "icon"


def load_char_map() -> dict:
    if not CHAR_MAP_FILE.exists():
        return {}
    with open(CHAR_MAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_icon(name: str) -> Path | None:
    """按角色名(中文或日文)找头像图片路径。"""
    cmap = load_char_map()
    for code, v in cmap.items():
        if name in (v.get("cn"), v.get("jp")):
            p = ICON_DIR / f"{code}.png"
            return p if p.exists() else None
    return None


def load_data() -> dict:
    merged = {}
    for name in DATA_FILES:
        fp = DATA_DIR / name
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                merged.update(json.load(f))
    return merged


def load_aliases() -> dict:
    """中文别名表: {别名: 目标名称}, 由用户/群友维护。"""
    if not ALIAS_FILE.exists():
        return {}
    with open(ALIAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_alias_index(data: dict) -> dict:
    index = {}
    name_to_key = {}
    for key, entry in data.items():
        index[key] = key
        index[entry["name"]] = key
        name_to_key[entry["name"]] = key
        for alias in entry.get("aliases", []):
            if alias:
                index[alias] = key

    for cn_alias, target_name in load_aliases().items():
        if target_name in name_to_key:
            index[cn_alias] = name_to_key[target_name]
    return index


def _format(entry: dict) -> str:
    return f"【{entry['name']}】\n{entry['content']}"


def search_local(keyword: str):
    """返回 (文本, 命中entry) 或 (None, None)。"""
    data = load_data()
    index = build_alias_index(data)

    if keyword in index:
        entry = data[index[keyword]]
        return _format(entry), entry

    substr = [k for k in index if keyword in k or k in keyword]
    if substr:
        entry = data[index[substr[0]]]
        return _format(entry), entry

    matches = get_close_matches(keyword, index.keys(), n=3, cutoff=0.5)
    if matches:
        entry = data[index[matches[0]]]
        others = "、".join(matches[1:]) if len(matches) > 1 else ""
        tail = f"\n\n(猜你想查「{matches[0]}」{('，其他相近：' + others) if others else ''})"
        return _format(entry) + tail, entry

    return None, None


def list_candidates(keyword: str) -> list[str]:
    data = load_data()
    index = build_alias_index(data)
    return get_close_matches(keyword, index.keys(), n=5, cutoff=0.3)


wiki = on_command("查", aliases={"wiki", "查询"}, priority=10, block=True)


@wiki.handle()
async def handle_wiki(event: MessageEvent, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    if not keyword:
        await wiki.finish("用法：/查 关键词，例如 /查 火球术")

    result, entry = search_local(keyword)
    if result:
        msg = Message(result)
        if entry and entry.get("type") == "英雄":
            icon = find_icon(entry["name"])
            if icon:
                msg = Message(result) + MessageSegment.image(icon)
        await wiki.finish(msg)

    try:
        online = await search_online(keyword)
    except Exception:
        online = None

    if online:
        await wiki.finish(online)

    candidates = list_candidates(keyword)
    if candidates:
        hint = "、".join(candidates)
        await wiki.finish(f"没找到「{keyword}」。你是不是想查：{hint}")
    await wiki.finish(f"没找到「{keyword}」相关内容，换个关键词试试？")


helper = on_command("帮助", aliases={"help", "菜单"}, priority=10, block=True)


@helper.handle()
async def handle_help():
    await helper.finish(
        "wiki 查询机器人\n"
        "/查 关键词  查角色/技能(附头像)\n"
        "/立绘 角色名  发送完整立绘\n"
        "例如：/查 赤司、/立绘 赤司\n"
        "支持中文名、日文名、别名、错别字模糊匹配。"
    )


illust = on_command("立绘", aliases={"图", "illust"}, priority=10, block=True)


@illust.handle()
async def handle_illust(args: Message = CommandArg()):
    name = args.extract_plain_text().strip()
    if not name:
        await illust.finish("用法：/立绘 角色名，例如 /立绘 赤司")

    code = resolve_code(name)
    if not code:
        await illust.finish(f"没找到「{name}」这个角色，试试用官方中文名？")

    path = fetch_illust(code)
    if path:
        await illust.finish(MessageSegment.image(path))
    await illust.finish(f"「{name}」暂时没有立绘（社群资料站还没收录）。")
