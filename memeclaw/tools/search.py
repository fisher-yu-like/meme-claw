"""Web search and scraping tools for meme data retrieval."""

import asyncio
from typing import Any

from memeclaw.config import config


async def web_search(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search the web for meme-related content.

    Uses DuckDuckGo (no API key needed) or SerpAPI as configured.
    Returns list of {title, url, snippet}.
    """
    if config.search_api == "serpapi" and config.serpapi_key:
        return await _serpapi_search(query, max_results)
    return await _duckduckgo_search(query, max_results)


# ── Platform-specific hot meme search queries ──

# With parallel per-platform judging, we can afford more search queries
# per platform — the LLM calls run concurrently, so extra search coverage
# doesn't add end-to-end latency.
PLATFORM_SEARCH_QUERIES = {
    "general": [
        "今天网上最火的是什么梗 出处 含义",
        "2026年5月 最新网络热梗 流行语 解释",
        "最近流行的梗 什么意思 怎么来的 出处",
        "互联网热梗 2026 流行语 含义 出处",
    ],
    "douyin": [
        "抖音 今天什么梗最火 意思",
        "抖音 最近流行梗 出处 怎么火的",
        "抖音热点 新梗 网络流行语 2026",
    ],
    "bilibili": [
        "B站 最近流行什么梗 解释",
        "bilibili 热门梗 出处 含义 2026",
        "B站弹幕 新梗 意思 最近流行",
    ],
    "weibo": [
        "微博 今天什么梗上热搜 解释",
        "微博热搜 梗 含义 出处 2026",
        "微博 流行语 网络热梗 最近",
    ],
    "xiaohongshu": [
        "小红书 最近流行的梗 含义 怎么来的",
        "小红书 网络热梗 流行语 2026",
        "小红书 新梗 出处 意思 流行",
    ],
}

# Max concurrent searches — raised from 4 to 6 since parallel judging
# means we want search results faster to feed the LLM pipeline
_SEARCH_SEMAPHORE = asyncio.Semaphore(6)
# Max results per platform after dedup — raised from 5 to 8 for broader coverage
_MAX_PER_PLATFORM = 8


async def search_platform_memes() -> list[dict[str, Any]]:
    """Search for hot memes across all configured platforms.

    Limited concurrency (semaphore) to avoid search-engine rate limiting.
    Results capped at _MAX_PER_PLATFORM per platform.
    """
    async def _search_one(query: str, platform: str) -> list[dict[str, Any]]:
        async with _SEARCH_SEMAPHORE:
            try:
                return await _search_with_source(query, platform)
            except Exception as e:
                print(f"[search] {platform} query '{query}' failed: {e}")
                return []

    tasks = []
    for platform, queries in PLATFORM_SEARCH_QUERIES.items():
        for q in queries:
            tasks.append(_search_one(q, platform))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge and cap per platform
    by_platform: dict[str, list] = {}
    for r in results:
        if isinstance(r, list):
            for item in r:
                plat = item.get("source_platform", "unknown")
                by_platform.setdefault(plat, []).append(item)

    merged = []
    for plat, items in by_platform.items():
        deduped = _deduplicate_results(items)
        merged.extend(deduped[:_MAX_PER_PLATFORM])

    return merged


async def _search_with_source(query: str, source: str) -> list[dict[str, Any]]:
    """Search and tag results with the source platform."""
    results = await web_search(query, max_results=3)
    for r in results:
        r["query"] = query
        r["source_platform"] = source
    return results


async def search_platform_memes_grouped() -> dict[str, list[dict[str, Any]]]:
    """Search for hot memes across all platforms, returning results grouped by platform.

    Each platform's results are kept separate so they can be judged independently
    by the LLM in parallel.
    """
    async def _search_one(query: str, platform: str) -> list[dict[str, Any]]:
        async with _SEARCH_SEMAPHORE:
            try:
                return await _search_with_source(query, platform)
            except Exception as e:
                print(f"[search] {platform} query '{query}' failed: {e}")
                return []

    tasks = []
    for platform, queries in PLATFORM_SEARCH_QUERIES.items():
        for q in queries:
            tasks.append(_search_one(q, platform))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Group by platform, deduplicate, and cap
    grouped: dict[str, list] = {}
    for r in results:
        if isinstance(r, list):
            for item in r:
                plat = item.get("source_platform", "unknown")
                grouped.setdefault(plat, []).append(item)

    for plat in grouped:
        grouped[plat] = _deduplicate_results(grouped[plat])[:_MAX_PER_PLATFORM]

    return grouped


async def search_social_context(meme_name: str) -> list[dict[str, Any]]:
    """Search for social background context around a meme.

    Searches for related news, social events, and cultural phenomena
    that contextualize the meme's emergence.
    """
    queries = [
        f"{meme_name} 梗 起源 出处",
        f"{meme_name} 流行 背景 社会事件",
        f"{meme_name} meme origin context",
    ]
    results = []
    for q in queries:
        results.extend(await web_search(q, max_results=5))
    return _deduplicate_results(results)


async def search_academic_papers(meme_name: str) -> list[dict[str, Any]]:
    """Search for relevant meme theory / academic papers."""
    queries = [
        f"meme theory {meme_name} cultural transmission",
        f"模因 传播 {meme_name} 网络文化",
        "internet meme culture social psychology research",
    ]
    results = []
    for q in queries:
        results.extend(await web_search(q, max_results=5))
    return _deduplicate_results(results)


async def _duckduckgo_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """Fallback: DuckDuckGo instant answer API (no key required)."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except ImportError:
        return [{"title": "Search unavailable", "url": "", "snippet": "Install duckduckgo_search package."}]


async def _serpapi_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """SerpAPI-based search."""
    import aiohttp

    params = {"q": query, "api_key": config.serpapi_key, "num": max_results, "engine": "google"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://serpapi.com/search", params=params) as resp:
            data = await resp.json()
    results = []
    for r in data.get("organic_results", [])[:max_results]:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "snippet": r.get("snippet", ""),
        })
    return results


def _deduplicate_results(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique
