"""
Search Service — SearXNG primary, DuckDuckGo fallback.
Includes a 5-minute in-memory TTL cache.
"""
import asyncio
import time
from typing import Dict, Optional

import httpx


CACHE_TTL = 300  # seconds


class _Cache:
    def __init__(self):
        self._store: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[str]:
        if key in self._store:
            val, ts = self._store[key]
            if time.monotonic() - ts < CACHE_TTL:
                return val
            del self._store[key]
        return None

    def set(self, key: str, value: str):
        self._store[key] = (value, time.monotonic())


class SearchService:
    def __init__(self, searxng_url: str = "http://localhost:8888"):
        self.searxng_url = searxng_url
        self._cache = _Cache()

    async def search(self, query: str, max_results: int = 4) -> str:
        cached = self._cache.get(query)
        if cached:
            return cached

        result = await self._searxng(query, max_results)
        if not result:
            result = await self._ddg(query, max_results)

        if result:
            self._cache.set(query, result)
        return result or "No results found."

    async def _searxng(self, query: str, n: int) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    f"{self.searxng_url}/search",
                    params={"q": query, "format": "json", "categories": "general"},
                )
                r.raise_for_status()
                results = r.json().get("results", [])[:n]
                if not results:
                    return None
                lines = []
                for i, item in enumerate(results, 1):
                    title   = item.get("title", "")
                    content = item.get("content", "")[:300]
                    url     = item.get("url", "")
                    lines.append(f"[{i}] {title}\n{content}\n{url}")
                return "\n\n".join(lines)
        except Exception:
            return None

    async def _ddg(self, query: str, n: int) -> Optional[str]:
        try:
            loop = asyncio.get_event_loop()

            def _sync():
                from duckduckgo_search import DDGS
                items = list(DDGS().text(query, max_results=n))
                if not items:
                    return None
                return "\n\n".join(
                    f"[{i+1}] {r['title']}\n{r['body']}" for i, r in enumerate(items)
                )

            return await loop.run_in_executor(None, _sync)
        except Exception as e:
            return f"Search error: {e}"


# Singleton — URL updated from env at server startup
search_service = SearchService()
