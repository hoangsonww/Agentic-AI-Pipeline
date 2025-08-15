import os
from typing import List, Dict, Optional

import httpx
import requests
from bs4 import BeautifulSoup

class WebSearch:
    """
    Google Programmable Search wrapper (CSE).
    """
    def __init__(self, api_key: str, engine_id: str):
        self.key = api_key
        self.cx = engine_id

    def search(self, q: str, num: int = 5) -> List[Dict]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": self.key, "cx": self.cx, "q": q}
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            items = r.json().get("items", [])[:num]
            out = []
            for it in items:
                out.append({
                    "title": it.get("title"),
                    "url": it.get("link"),
                    "snippet": it.get("snippet", "")
                })
            return out

def fetch_page_text(url: str, timeout: int = 20) -> Optional[str]:
    """
    Fetch a URL and extract visible text via BeautifulSoup.
    """
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "agentic-rag/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text("\n")
        # collapse whitespace
        lines = [ln.strip() for ln in text.splitlines()]
        text = "\n".join([ln for ln in lines if ln])
        return text[:20000]  # cap to 20k chars
    except Exception:
        return None
