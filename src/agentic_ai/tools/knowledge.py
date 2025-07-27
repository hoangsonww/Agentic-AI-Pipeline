from __future__ import annotations
from langchain.tools import BaseTool
import json
from ..layers import memory as mem


class KbSearch(BaseTool):
    name = "kb_search"
    description = "Search the internal knowledge base (vector store). Input: query string. Output: JSON list of {id, text, metadata}."

    def _run(self, query: str) -> str:
        res = mem.kb_search(query, k=5)
        return json.dumps(res, ensure_ascii=False)


class KbAdd(BaseTool):
    name = "kb_add"
    description = "Add a document to internal KB. Input JSON {id, text, metadata}. Output: ok message."

    def _run(self, spec: str) -> str:
        obj = json.loads(spec)
        mem.kb_add(obj["id"], obj["text"], obj.get("metadata"))
        return "ok"
