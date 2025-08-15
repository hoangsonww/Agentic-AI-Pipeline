from typing import List, Dict, Any
from agents.base import Agent
from core.structs import AgentResult, Evidence
from core.vector import FAISSIndex
from core.tools import WebSearch, fetch_page_text

class VectorRetriever(Agent):
    name: str = "vector_retriever"

    def __init__(self, index: FAISSIndex):
        super().__init__()
        self.index = index

    def run(self, query: str, k: int = 8) -> AgentResult:
        hits = self.index.search(query, k=k)
        ev = [Evidence(**h) for h in hits]
        return AgentResult(output=hits, evidence=ev)

class WebRetriever(Agent):
    name: str = "web_retriever"

    def __init__(self, web: WebSearch):
        super().__init__()
        self.web = web

    def run(self, query: str, k: int = 5) -> AgentResult:
        if not self.web:
            return AgentResult(output=[], evidence=[])
        results = self.web.search(query, num=k)
        enriched = []
        for r in results:
            content = fetch_page_text(r["url"]) or r.get("snippet", "")
            enriched.append({
                "doc_id": r["url"],
                "chunk_id": "0",
                "text": content[:2000],  # cap to keep evidence concise
                "meta": {"uri": r["url"], "title": r.get("title")}
            })
        ev = [Evidence(**h) for h in enriched]
        return AgentResult(output=enriched, evidence=ev)
