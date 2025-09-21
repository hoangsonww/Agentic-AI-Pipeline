from __future__ import annotations

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


async def fetch_page(url: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
    text = trafilatura.extract(resp.text, url=url)
    if not text:
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
    return text or ""

