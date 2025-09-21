"""
Replay system for deterministic reproduction of agent runs.
Mocks tool calls using recorded trace data.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass

from .trace import read_trace, TraceEvent, trace_run
from ..config import settings
from ..layers import memory as mem


@dataclass
class ReplaySession:
    """Manages replay of a single trace"""
    trace_events: List[TraceEvent]
    tool_responses: Dict[str, Any] = None
    current_index: int = 0
    
    def __post_init__(self):
        """Build lookup tables for efficient replay"""
        if self.tool_responses is None:
            self.tool_responses = {}
        
        # Build mapping of tool requests to responses
        pending_requests = {}
        
        for event in self.trace_events:
            if event.event_type == "tool_request":
                tool_name = event.data.get("tool_name")
                args_hash = event.data.get("args_hash")
                if tool_name and args_hash:
                    pending_requests[args_hash] = {
                        "tool_name": tool_name,
                        "args": event.data.get("args", {}),
                        "timestamp": event.timestamp
                    }
            
            elif event.event_type == "tool_response":
                tool_name = event.data.get("tool_name")
                # Try to match with recent request by tool name and timing
                matching_hash = None
                min_time_diff = float('inf')
                
                for hash_key, request in pending_requests.items():
                    if (request["tool_name"] == tool_name and 
                        event.timestamp >= request["timestamp"]):
                        time_diff = event.timestamp - request["timestamp"]
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            matching_hash = hash_key
                
                if matching_hash:
                    request = pending_requests.pop(matching_hash)
                    self.tool_responses[matching_hash] = {
                        "tool_name": tool_name,
                        "args": request["args"],
                        "result": event.data.get("result"),
                        "error": event.data.get("error"),
                        "duration_ms": event.duration_ms
                    }


class MockTool:
    """Mock tool that returns responses from trace data"""
    
    def __init__(self, tool_name: str, replay_session: ReplaySession):
        self.name = tool_name
        self.description = f"Mock {tool_name} (replay mode)"
        self.replay_session = replay_session
    
    def _run(self, **kwargs) -> str:
        """Return recorded response for this tool call"""
        import hashlib
        
        # Generate same hash as during recording
        args_hash = hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()[:8]
        
        # Look up response from recorded trace
        if args_hash in self.replay_session.tool_responses:
            response_data = self.replay_session.tool_responses[args_hash]
            
            if response_data.get("error"):
                raise Exception(response_data["error"])
            
            result = response_data.get("result")
            return str(result) if result is not None else ""
        
        # Fallback if no exact match found
        print(f"Warning: No recorded response found for {self.name}({kwargs})")
        return f"[REPLAY: No recorded response for {self.name}]"


class ReplayEngine:
    """Core replay engine that orchestrates mock execution"""
    
    def __init__(self, trace_path: Path):
        self.trace_path = trace_path
        self.events = read_trace(trace_path)
        self.replay_session = ReplaySession(self.events)
        
        # Extract original chat info
        self.original_chat_id = None
        self.original_run_id = None
        self.original_user_message = None
        
        for event in self.events:
            if event.event_type == "run_start":
                self.original_chat_id = event.data.get("chat_id")
                self.original_run_id = event.data.get("run_id")
            elif event.event_type == "state_transition" and "user_message" in event.data:
                self.original_user_message = event.data["user_message"]
                break
    
    def create_mock_tools(self) -> List[MockTool]:
        """Create mock tools based on trace data"""
        tool_names = set()
        
        for event in self.events:
            if event.event_type == "tool_request":
                tool_name = event.data.get("tool_name")
                if tool_name:
                    tool_names.add(tool_name)
        
        return [MockTool(name, self.replay_session) for name in tool_names]
    
    async def replay_chat(self, new_chat_id: Optional[str] = None, enable_tracing: bool = True) -> AsyncIterator[str]:
        """Replay the chat with mock tools"""
        if not self.original_user_message:
            raise ValueError("Could not extract original user message from trace")
        
        chat_id = new_chat_id or f"replay_{self.original_chat_id}"
        
        # Create mock tools
        mock_tools = self.create_mock_tools()
        
        # Replace the tool registry temporarily
        from ..layers.tools import registry as original_registry
        from ..layers.reasoning import build_graph
        
        # Save original settings
        original_trace_setting = settings.ENABLE_TRACING
        
        try:
            # Enable tracing for replay if requested
            if enable_tracing:
                settings.ENABLE_TRACING = True
            
            # Create a new graph with mock tools
            mock_graph = build_graph(mock_tools)
            
            # Save user message to memory
            mem.save_turn(chat_id, "user", self.original_user_message)
            
            # Create initial state
            from langchain_core.messages import HumanMessage
            state = {
                "messages": [HumanMessage(content=self.original_user_message)],
                "plan": "",
                "next_action": "",
                "citations": [],
                "done": False
            }
            
            # Run with tracing
            with trace_run(chat_id) as tracer:
                if tracer:
                    tracer.log_state_transition("init", "replay_start", {
                        "original_trace": str(self.trace_path),
                        "original_chat_id": self.original_chat_id,
                        "original_run_id": self.original_run_id
                    })
                
                last_ai = None
                async for ev in mock_graph.astream(state, stream_mode="values"):
                    msgs = ev.get("messages") or []
                    if msgs and hasattr(msgs[-1], 'content'):
                        content = msgs[-1].content
                        if content != last_ai:  # Only yield new content
                            yield content
                            last_ai = content
                
                # Save final response
                if last_ai:
                    mem.save_turn(chat_id, "assistant", last_ai)
                    
                if tracer:
                    tracer.log_state_transition("replay_complete", "end", {"final_response": last_ai})
        
        finally:
            # Restore original settings
            settings.ENABLE_TRACING = original_trace_setting
    
    def get_replay_info(self) -> Dict[str, Any]:
        """Get information about the replay session"""
        tool_calls = sum(1 for e in self.events if e.event_type == "tool_request")
        node_transitions = sum(1 for e in self.events if e.event_type in ["node_start", "node_end"])
        
        return {
            "original_chat_id": self.original_chat_id,
            "original_run_id": self.original_run_id,
            "original_message": self.original_user_message,
            "total_events": len(self.events),
            "tool_calls": tool_calls,
            "node_transitions": node_transitions,
            "mock_tools": len(self.replay_session.tool_responses),
            "trace_file": str(self.trace_path)
        }


async def replay_trace(trace_path: Path, new_chat_id: Optional[str] = None, 
                      enable_tracing: bool = True) -> str:
    """Convenience function to replay a trace and return the full response"""
    engine = ReplayEngine(trace_path)
    
    chunks = []
    async for chunk in engine.replay_chat(new_chat_id, enable_tracing):
        chunks.append(chunk)
    
    return ''.join(chunks)


def compare_traces(original_path: Path, replay_path: Path) -> Dict[str, Any]:
    """Compare original and replay traces for differences"""
    original_events = read_trace(original_path)
    replay_events = read_trace(replay_path)
    
    # Extract key sequences
    def extract_sequence(events):
        return [
            (e.event_type, e.node_name, e.data.get("tool_name"))
            for e in events
            if e.event_type in ["node_start", "tool_request", "state_transition"]
        ]
    
    original_sequence = extract_sequence(original_events)
    replay_sequence = extract_sequence(replay_events)
    
    # Find differences
    sequence_match = original_sequence == replay_sequence
    
    # Compare tool calls
    original_tools = [
        e.data.get("tool_name") for e in original_events 
        if e.event_type == "tool_request"
    ]
    replay_tools = [
        e.data.get("tool_name") for e in replay_events
        if e.event_type == "tool_request"
    ]
    
    return {
        "sequence_match": sequence_match,
        "original_events": len(original_events),
        "replay_events": len(replay_events),
        "original_tools": original_tools,
        "replay_tools": replay_tools,
        "tools_match": original_tools == replay_tools,
        "differences": {
            "sequence": list(set(original_sequence) - set(replay_sequence)),
            "missing_in_replay": list(set(original_sequence) - set(replay_sequence)),
            "extra_in_replay": list(set(replay_sequence) - set(original_sequence))
        }
    }