import json
import os
from typing import List, Dict, Any

class SessionMemory:
    """
    Simple append-only JSONL memory persisted in a temp file per session.
    No external services needed; safe default that always works.
    """
    def __init__(self, base_dir: str = ".session_memory"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self.base_dir, f"{session_id}.jsonl")

    def append(self, session_id: str, role: str, content: str):
        item = {"role": role, "content": content}
        with open(self._path(session_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def load(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        path = self._path(session_id)
        if not os.path.exists(path):
            return []
        out = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out[-limit:]

    def summary_text(self, session_id: str, limit: int = 24) -> str:
        msgs = self.load(session_id, limit=limit)
        return "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
