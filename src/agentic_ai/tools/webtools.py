from __future__ import annotations
from langchain.tools import BaseTool
from duckduckgo_search import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx, trafilatura, json


class WebSearch(BaseTool):
    name: str = "web_search"
    description: str = "Search the web. Input: a natural language query. Output: JSON list of {title, url, snippet}."

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def _run(self, query: str) -> str:
        with DDGS() as d:
            results = d.text(query, max_results=8)
        return json.dumps(list(results), ensure_ascii=False)


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
