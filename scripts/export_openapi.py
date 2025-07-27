from __future__ import annotations
import json
from agentic_ai.app import app

if __name__ == "__main__":
    with open("openapi.json","w",encoding="utf-8") as f:
        json.dump(app.openapi(), f, ensure_ascii=False, indent=2)
    print("openapi.json written")
