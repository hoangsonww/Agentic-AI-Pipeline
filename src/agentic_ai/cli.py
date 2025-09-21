from __future__ import annotations

import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Iterable

import anyio
import httpx

from .layers import memory as mem


def _iter_files(root: Path, exts: set[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def cmd_ingest(path: str) -> None:
    root = Path(path)
    if not root.exists():
        print(f"path not found: {path}", file=sys.stderr)
        sys.exit(2)
    exts = {".txt", ".md"}
    total = 0
    for fp in _iter_files(root, exts):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        text = text[:10000]
        meta = {"uri": str(fp), "title": fp.name}
        mem.kb_add(str(fp), text, meta)
        total += 1
    print(f"ingested {total} files from {path}")


async def cmd_demo(prompt: str, base_url: str = "http://127.0.0.1:8000") -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{base_url}/api/new_chat"); r.raise_for_status()
        chat_id = r.json()["chat_id"]
        r = await client.post(f"{base_url}/api/chat", json={"chat_id": chat_id, "message": prompt})
        r.raise_for_status()
        async for chunk in r.aiter_text():
            for block in chunk.split("\n\n"):
                if not block.strip():
                    continue
                ev = None; data = None
                for line in block.splitlines():
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:]
                if ev == "token" and data:
                    print(data, end="")
                elif ev == "done":
                    print("\n--- done ---")
                    return


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m agentic_ai.cli [ingest <dir> | demo <prompt>]")
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "ingest":
        if len(sys.argv) < 3:
            print("usage: python -m agentic_ai.cli ingest <dir>")
            sys.exit(2)
        cmd_ingest(sys.argv[2])
    elif cmd == "demo":
        prompt = " ".join(sys.argv[2:]) or "Build a competitive briefing on ACME Robotics and draft a short outreach email."
        anyio.run(cmd_demo, prompt)
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()

