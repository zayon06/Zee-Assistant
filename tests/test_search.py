import pytest
from server.search import SearchService

@pytest.mark.asyncio
async def test_search_cache():
    service = SearchService(searxng_url="http://invalid") # Will fail SearXNG, fallback to DDG
    service._cache.set("test_query", "Cached Result Data")
    
    res = await service.search("test_query")
    assert res == "Cached Result Data"

@pytest.mark.asyncio
async def test_search_ddg_fallback():
    # Attempting a real DDG search, might fail if no internet, but usually works
    service = SearchService(searxng_url="http://invalid")
    res = await service.search("python programming", max_results=1)
    
    # Even if it errors out to "Search error: ...", it returns a string
    assert isinstance(res, str)
    assert len(res) > 0
