from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage

from .infra.logging import logger
from .layers import memory as mem
from .layers.reasoning import build_graph
from .layers.tools import registry

# Lazy graph initialization — avoids API-key validation at import time
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _tools = registry()
        _graph = build_graph(_tools)
        logger.info("LangGraph agent graph compiled")
    return _graph


async def run_chat(chat_id: str, user_text: str) -> AsyncIterator[str]:
    """Stream an agent response for one user message."""
    mem.save_turn(chat_id, "user", user_text)
    graph = _get_graph()
    state = {
        "messages": [HumanMessage(content=user_text)],
        "plan": "",
        "next_action": "",
        "citations": [],
        "done": False,
    }
    last_ai = None
    async for ev in graph.astream(state, stream_mode="values"):
        msgs = ev.get("messages") or []
        if msgs and isinstance(msgs[-1], AIMessage):
            content = msgs[-1].content
            last_ai = content
            yield content
    if last_ai:
        mem.save_turn(chat_id, "assistant", last_ai)
