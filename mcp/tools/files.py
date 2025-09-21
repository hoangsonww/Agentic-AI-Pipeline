from __future__ import annotations

from pathlib import Path

BASE = Path("data/agent_output").resolve()
BASE.mkdir(parents=True, exist_ok=True)


def _safe_path(rel_path: str) -> Path:
    p = (BASE / rel_path).resolve()
    if not str(p).startswith(str(BASE)):
        raise ValueError("path escapes sandbox")
    return p


def write_file(path: str, content: str) -> dict:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p)}


def read_file(path: str) -> dict:
    p = _safe_path(path)
    if not p.exists():
        return {"ok": False, "error": "not found"}
    return {"ok": True, "path": str(p), "content": p.read_text(encoding="utf-8", errors="ignore")}

