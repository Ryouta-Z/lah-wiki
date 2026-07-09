import json
from pathlib import Path

import httpx

CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "data" / "wiki_config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"online_enabled": False}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def search_online(keyword: str) -> str | None:
    cfg = load_config()
    if not cfg.get("online_enabled"):
        return None

    endpoint = cfg["api_endpoint"]
    headers = {"User-Agent": cfg.get("user_agent", "LW-WIKI-Bot/0.1")}
    max_len = cfg.get("summary_max_length", 300)

    title = await _resolve_title(endpoint, headers, keyword)
    if not title:
        return None

    extract = await _fetch_extract(endpoint, headers, title)
    if not extract:
        return None

    if len(extract) > max_len:
        extract = extract[:max_len].rstrip() + "..."

    page_url = cfg.get("site_base_url", "").rstrip("/") + "/" + title.replace(" ", "_")
    return f"【{title}】\n{extract}\n\n详见：{page_url}"


async def _resolve_title(endpoint: str, headers: dict, keyword: str) -> str | None:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": keyword,
        "srlimit": 1,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(endpoint, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("query", {}).get("search", [])
    if not results:
        return None
    return results[0]["title"]


async def _fetch_extract(endpoint: str, headers: dict, title: str) -> str | None:
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": 1,
        "explaintext": 1,
        "titles": title,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(endpoint, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for _, page in pages.items():
        extract = page.get("extract", "").strip()
        if extract:
            return extract
    return None
