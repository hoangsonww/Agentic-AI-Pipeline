from __future__ import annotations

import os

import httpx
import trafilatura
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


async def search_ddg(q: str, max_results: int = 5):
    with DDGS() as ddgs:
        try:
            return list(ddgs.text(q, max_results=max_results))
        except Exception:
            return []


async def search_tavily(q: str, max_results: int = 5):
    """Search using the Tavily API, returning results normalised to {title, href, body}."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    try:
        response = client.search(query=q, max_results=max_results)
    except Exception:
        return []
    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "href": r.get("url", ""),
            "body": r.get("content", ""),
        })
    return results


async def search_web(q: str, max_results: int = 5):
    """Dispatch to the configured search provider (duckduckgo or tavily)."""
    provider = os.environ.get("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider == "tavily":
        return await search_tavily(q, max_results=max_results)
    return await search_ddg(q, max_results=max_results)


async def fetch_page(url: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
    text = trafilatura.extract(resp.text, url=url)
    if not text:
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
    return text or ""
