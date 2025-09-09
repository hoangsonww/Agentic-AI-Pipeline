from __future__ import annotations
from typing import AsyncIterator
from langchain_core.messages import HumanMessage, AIMessage
from .layers.reasoning import build_graph
from .layers.tools import registry
from .layers import memory as mem
from .infra.logging import logger
from .infra.trace import trace_run, get_current_tracer

_tools = registry()
_graph = build_graph(_tools)


async def run_chat(chat_id: str, user_text: str) -> AsyncIterator[str]:
    with trace_run(chat_id) as tracer:
        # Persist user message
        mem.save_turn(chat_id, "user", user_text)
        state = {"messages": [HumanMessage(content=user_text)], "plan": "", "next_action": "", "citations": [],
                 "done": False}
        
        if tracer:
            tracer.log_state_transition("init", "start", {"user_message": user_text})
        
        last_ai = None
        async for ev in _graph.astream(state, stream_mode="values"):
            msgs = ev.get("messages") or []
            if msgs and isinstance(msgs[-1], AIMessage):
                content = msgs[-1].content
                last_ai = content
                yield content
        
        # Persist final assistant content
        if last_ai:
            mem.save_turn(chat_id, "assistant", last_ai)
            
        if tracer:
            tracer.log_state_transition("complete", "end", {"final_response": last_ai})
