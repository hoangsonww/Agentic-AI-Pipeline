from __future__ import annotations

import json
import os

import httpx
import trafilatura
from duckduckgo_search import DDGS
from langchain.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential


class WebSearch(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web. Input: a natural language query. "
        "Output: JSON list of {title, url, snippet}."
    )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def _run(self, query: str) -> str:
        with DDGS() as d:
            results = d.text(query, max_results=8)
        return json.dumps(list(results), ensure_ascii=False)


class TavilyWebSearch(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web. Input: a natural language query. "
        "Output: JSON list of {title, url, snippet}."
    )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def _run(self, query: str) -> str:
        from tavily import TavilyClient

        client = TavilyClient()
        response = client.search(query=query, max_results=8)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]
        return json.dumps(results, ensure_ascii=False)


def get_web_search_tool() -> BaseTool:
    """Return the active web search tool based on SEARCH_PROVIDER env var."""
    provider = os.environ.get("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider == "tavily":
        return TavilyWebSearch()
    return WebSearch()


class WebFetch(BaseTool):
    name: str = "web_fetch"
    description: str = "Fetch a URL and extract main readable text. Input: URL. Output: text."

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def _run(self, url: str) -> str:
        with httpx.Client(follow_redirects=True, timeout=20) as client:
            r = client.get(url)
            r.raise_for_status()
            extracted = trafilatura.extract(r.text, include_comments=False, include_tables=False)
            return extracted or r.text[:6000]
