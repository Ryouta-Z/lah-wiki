"""基于 Edge(微软) 免费翻译的日译中工具, 带本地磁盘缓存。

无需 API key, 国内可直连。用于把没有社区中文翻译的日文技能描述译成中文。
"""
import json
import time
from pathlib import Path

import httpx

AUTH_URL = "https://edge.microsoft.com/translate/auth"
TRANS_URL = (
    "https://api-edge.cognitive.microsofttranslator.com/translate"
    "?api-version=3.0&from=ja&to=zh-Hans"
)
CACHE_FILE = Path(__file__).parent.parent / "data" / "mtl_cache.json"


class Translator:
    """带缓存的批量日译中翻译器。"""

    def __init__(self):
        self.cache: dict = {}
        if CACHE_FILE.exists():
            self.cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        self._token = ""
        self._token_at = 0.0

    def _get_token(self) -> str:
        # token 有效期约 10 分钟, 提前刷新
        if not self._token or time.time() - self._token_at > 500:
            self._token = httpx.get(AUTH_URL, timeout=10.0).text
            self._token_at = time.time()
        return self._token

    def _post(self, texts: list[str]) -> list[str]:
        body = [{"Text": t} for t in texts]
        headers = {
            "Authorization": "Bearer " + self._get_token(),
            "Content-Type": "application/json",
        }
        for attempt in range(4):
            try:
                r = httpx.post(TRANS_URL, headers=headers, json=body, timeout=20.0)
                if r.status_code == 401:
                    self._token = ""
                    headers["Authorization"] = "Bearer " + self._get_token()
                    continue
                r.raise_for_status()
                return [d["translations"][0]["text"] for d in r.json()]
            except httpx.HTTPError as e:
                print(f"    翻译请求失败({attempt + 1}/4): {type(e).__name__}, 重试...")
                time.sleep(1.5)
        raise RuntimeError("翻译请求多次失败")

    def save(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def translate_all(self, texts: list[str]) -> dict:
        """翻译一批日文文本, 返回 {原文: 译文}。命中缓存的不再请求。"""
        uniq = [t for t in dict.fromkeys(texts) if t and t not in self.cache]
        if uniq:
            print(f"  需翻译 {len(uniq)} 条(其余命中缓存)...")
        batch, size = [], 0
        done = 0
        for text in uniq:
            # Edge 单次请求限制: 条数和总字符数都不宜过大
            if batch and (len(batch) >= 20 or size + len(text) > 4000):
                self._flush(batch)
                done += len(batch)
                print(f"    已翻译 {done}/{len(uniq)}")
                batch, size = [], 0
            batch.append(text)
            size += len(text)
        if batch:
            self._flush(batch)
            done += len(batch)
            print(f"    已翻译 {done}/{len(uniq)}")
        if uniq:
            self.save()
        return {t: self.cache.get(t, t) for t in texts}

    def _flush(self, batch: list[str]):
        results = self._post(batch)
        for src, dst in zip(batch, results):
            self.cache[src] = dst
