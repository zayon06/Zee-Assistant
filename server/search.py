"""
Search Service — DuckDuckGo (ddgs) with 5-minute in-memory TTL cache.
SearXNG Docker dependency removed. Falls back gracefully on error.
"""
import asyncio
import time
from typing import Dict, Optional


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
    def __init__(self):
        self._cache = _Cache()

    async def search(self, query: str, max_results: int = 4) -> str:
        cached = self._cache.get(query)
        if cached:
            return cached

        result = await self._ddg(query, max_results)
        if result:
            self._cache.set(query, result)
        return result or "No results found."

    async def _ddg(self, query: str, n: int) -> Optional[str]:
        try:
            loop = asyncio.get_event_loop()

            def _sync():
                try:
                    from ddgs import DDGS
                except ImportError:
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


# Singleton
search_service = SearchService()
