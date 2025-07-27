from __future__ import annotations
import time
from collections import defaultdict

# Simple token bucket (per chat_id)
_BUCKETS: dict[str, tuple[float,int]] = defaultdict(lambda: (time.time(), 5))  # (last_refill, tokens)
RATE = 5          # tokens
PER_SECONDS = 10  # window

def allow(chat_id: str) -> bool:
    now = time.time()
    last, tokens = _BUCKETS[chat_id]
    # refill
    new_tokens = min(RATE, tokens + int((now - last) / PER_SECONDS) * RATE)
    if new_tokens <= 0:
        _BUCKETS[chat_id] = (now, new_tokens)
        return False
    _BUCKETS[chat_id] = (now, new_tokens - 1)
    return True
