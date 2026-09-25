from __future__ import annotations

import json
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


async def search_youcom(q: str, max_results: int = 5):
    """Search using You.com MCP, returning results normalised to {title, href, body}.

    Uses the keyless ``?profile=free`` endpoint when ``YOUCOM_API_KEY`` is unset.
    """
    api_key = os.environ.get("YOUCOM_API_KEY", "")
    if api_key:
        url = "https://api.you.com/mcp"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    else:
        url = "https://api.you.com/mcp?profile=free"
        headers = {"Content-Type": "application/json"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "you-search",
            "arguments": {"query": q, "num_results": max_results},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()
    except Exception:
        return []

    result = data.get("result", {})
    content = result.get("content", [])

    items = []
    for entry in content:
        if entry.get("type") != "text":
            continue
        raw = entry.get("text", "")
        if not raw:
            continue
        # Try JSON array of result objects
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for r in parsed:
                    if isinstance(r, dict) and ("url" in r or "link" in r):
                        items.append(_normalise(r))
                if items:
                    return items
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: try a single JSON object
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(obj, dict) and ("url" in obj or "link" in obj):
                items.append(_normalise(obj))
                return items
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: structured URL extraction from markdown
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("[") and "](" in line and ")" in line:
                title = line[1: line.index("](")]
                href = line[line.index("](") + 2: line.index(")")]
                items.append({"title": title, "href": href, "body": ""})
            elif "http" in line and " - " in line:
                parts = line.split(" - ", 1)
                urls = [w for w in parts[0].split() if w.startswith("http")]
                if urls:
                    items.append({
                        "title": parts[0].replace(urls[0], "").strip(),
                        "href": urls[0],
                        "body": parts[1] if len(parts) > 1 else "",
                    })

    return items


def _normalise(r: dict) -> dict:
    """Normalise a search result dict to {title, href, body}."""
    return {
        "title": r.get("title", "") or "",
        "href": r.get("url") or r.get("link") or "",
        "body": r.get("snippet") or r.get("description") or r.get("content") or "",
    }


async def search_web(q: str, max_results: int = 5):
    """Dispatch to the configured search provider."""
    provider = os.environ.get("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider == "youcom":
        return await search_youcom(q, max_results=max_results)
    return await search_ddg(q, max_results=max_results)


async def fetch_page(url: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
    text = trafilatura.extract(resp.text, url=url)
    if not text:
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
    return text or ""
