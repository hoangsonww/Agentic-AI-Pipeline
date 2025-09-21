from __future__ import annotations

from typing import Any, Dict, List

from agentic_ai.layers import memory as mem


def kb_add(doc_id: str | None, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    did = doc_id or ""
    if not did:
        import uuid
        did = f"doc:{uuid.uuid4()}"
    mem.kb_add(did, text, metadata or {})
    return {"ok": True, "id": did}


def kb_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    return mem.kb_search(query, k=k)

