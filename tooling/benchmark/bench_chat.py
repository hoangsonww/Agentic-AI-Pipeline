from __future__ import annotations
import time, statistics, json, asyncio, sys, httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PROMPT = "Give me two concise bullets on AMR vendors with a citation."
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

async def run_once(client: httpx.AsyncClient):
    t0 = time.perf_counter()
    new = await client.get(f"{BASE}/api/new_chat")
    new.raise_for_status()
    chat_id = new.json()["chat_id"]
    r = await client.post(f"{BASE}/api/chat", json={"chat_id": chat_id, "message": PROMPT})
    r.raise_for_status()
    # consume SSE body purely to completion
    _ = r.text
    return time.perf_counter() - t0

async def main():
    times = []
    async with httpx.AsyncClient(timeout=60.0) as c:
        for _ in range(RUNS):
            dt = await run_once(c)
            print(f"Run: {dt:.2f}s")
            times.append(dt)
    print(json.dumps({
        "runs": RUNS,
        "mean": statistics.mean(times),
        "p95": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
        "min": min(times),
        "max": max(times)
    }, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
