from agentic_ai.layers import memory as mem


def test_vector_kb_add_and_search():
    mem.kb_add("doc:hello", "hello world vector test", {"t": "unit"})
    hits = mem.kb_search("hello", k=3)
    assert hits and any("hello world" in h["text"] for h in hits)


def test_sql_roundtrip_chat_history():
    mem.save_turn("chat-x", "user", "hi")
    mem.save_turn("chat-x", "assistant", "hello")
    hist = mem.history("chat-x")
    assert len(hist) >= 2 and hist[0]["role"] == "user"
