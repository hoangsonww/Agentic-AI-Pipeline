from __future__ import annotations

import asyncio
import json
import sys
import threading
import types
import logging
from pathlib import Path
from typing import Any

from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage


_TOOL_IO: "ToolIO | None" = None
_TASK_USER_TEXT = ""


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class ToolIO:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 1

    def call(self, name: str, args: dict[str, Any]) -> Any:
        with self._lock:
            call_id = f"c{self._next_id}"
            self._next_id += 1
            _send({"type": "tool_call", "name": name, "call_id": call_id, "args": args})

            while True:
                line = sys.stdin.readline()
                if not line:
                    raise RuntimeError("Runner closed stdin while waiting for tool_result")
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("type") != "tool_result":
                    continue
                if msg.get("call_id") != call_id:
                    continue
                if not msg.get("ok", False):
                    raise RuntimeError(msg.get("error") or "tool call failed")
                return msg.get("result")


class RunLedgerWebSearch(BaseTool):
    name: str = "web_search"
    description: str = "Search the web (replayed by RunLedger). Input: query string."

    def _run(self, query: str) -> str:
        if _TOOL_IO is None:
            raise RuntimeError("ToolIO not initialized")
        result = _TOOL_IO.call(self.name, {"query": query})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    async def _arun(self, query: str) -> str:
        return await asyncio.to_thread(self._run, query)


def _messages_text(messages: Any) -> str:
    if isinstance(messages, list):
        parts = [getattr(m, "content", "") for m in messages]
    else:
        parts = [getattr(messages, "content", "")]
    return "\n".join(str(p) for p in parts if p)


def _find_repo_root(script_path: Path) -> Path:
    for parent in script_path.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    parents = list(script_path.parents)
    return parents[3] if len(parents) > 3 else script_path.parent


def _last_user_text(messages: Any) -> str:
    if not isinstance(messages, list):
        messages = [messages]
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content).strip()
    return ""


class FakeLLM:
    def __init__(self, bound_tools: list[BaseTool] | None = None) -> None:
        self._bound_tools = bound_tools or []

    def bind_tools(self, tools: list[BaseTool]) -> "FakeLLM":
        return FakeLLM(bound_tools=list(tools))

    def invoke(self, messages: Any) -> AIMessage:
        text = _messages_text(messages)
        if "Produce a 3-6 step action plan" in text:
            return AIMessage(content="1) Search for info\n2) Summarize findings")
        if "Choose ONE token from" in text:
            return AIMessage(content="search")
        if "You MUST call exactly one tool" in text:
            user_text = _TASK_USER_TEXT or _last_user_text(messages)
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "web_search", "args": {"query": user_text}, "id": "runledger_t1"}
                ],
            )
        if "write BRIEFING" in text:
            return AIMessage(
                content=(
                    "BRIEFING\n"
                    "- Deterministic demo run (stubbed model).\n"
                    "Citations:\n"
                    "- https://example.com\n"
                )
            )
        return AIMessage(content="finalize")


def _install_stubs() -> None:
    logging_stub = types.ModuleType("agentic_ai.infra.logging")
    adapter_logger = logging.getLogger("runledger.adapter")
    adapter_logger.handlers.clear()
    adapter_logger.addHandler(logging.StreamHandler(sys.stderr))
    adapter_logger.setLevel(logging.INFO)
    adapter_logger.propagate = False
    logging_stub.logger = adapter_logger
    logging_stub.setup_logging = lambda *args, **kwargs: adapter_logger
    sys.modules["agentic_ai.infra.logging"] = logging_stub

    memory_stub = types.ModuleType("agentic_ai.layers.memory")

    def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    memory_stub.save_turn = _noop
    memory_stub.kb_search = lambda *args, **kwargs: []
    memory_stub.kb_add = _noop
    memory_stub.history = lambda *args, **kwargs: []
    memory_stub.add_feedback = _noop
    sys.modules["agentic_ai.layers.memory"] = memory_stub

    tools_stub = types.ModuleType("agentic_ai.layers.tools")
    tools_stub.registry = lambda: [RunLedgerWebSearch()]
    sys.modules["agentic_ai.layers.tools"] = tools_stub


async def _run_chat(chat_id: str, user_text: str) -> str:
    from agentic_ai.graph import run_chat

    last = ""
    async for chunk in run_chat(chat_id=chat_id, user_text=user_text):
        if chunk:
            last = chunk
    return last


def main() -> int:
    global _TOOL_IO, _TASK_USER_TEXT

    task_start: dict[str, Any] | None = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("type") == "task_start":
            task_start = msg
            break

    if task_start is None:
        return 0

    input_payload = task_start.get("input") or {}
    chat_id = str(input_payload.get("chat_id") or task_start.get("task_id") or "runledger")
    user_text = str(input_payload.get("user_text") or input_payload.get("ticket") or "")
    _TASK_USER_TEXT = user_text

    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root / "src"))

    _TOOL_IO = ToolIO()
    _install_stubs()

    from agentic_ai.layers import reasoning

    reasoning._llm = lambda: FakeLLM()

    reply = asyncio.run(_run_chat(chat_id, user_text))
    _send({"type": "final_output", "output": {"category": "demo", "reply": reply}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
