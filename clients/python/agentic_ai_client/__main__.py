from __future__ import annotations
import anyio, os, sys
from .client import AgenticAIClient

async def _run():
    base = os.environ.get("BASE_URL","http://127.0.0.1:8000")
    prompt = " ".join(sys.argv[1:]) or "Build a competitive briefing on ACME Robotics and draft a short outreach email."
    async with AgenticAIClient(base) as c:
        meta = await c.new_chat()
        chat_id = meta["chat_id"]
        async def on_tok(t: str):
            print(t, end="", flush=True)
        await c.chat_stream(message=prompt, chat_id=chat_id, on_token=lambda t: print(t, end=""))
        print("\\n--- done ---")

def main():
    anyio.run(_run)

if __name__ == "__main__":
    main()
