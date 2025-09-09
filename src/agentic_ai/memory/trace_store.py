"""JSONL trace storage for deterministic replay."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator
from dataclasses import dataclass, asdict
from enum import Enum


class TraceEventType(str, Enum):
    """Types of trace events."""
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_PROMPT = "llm_prompt"
    LLM_OUTPUT = "llm_output"


@dataclass
class TraceEvent:
    """A single trace event."""
    timestamp: str
    event_type: TraceEventType
    chat_id: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    node: Optional[str] = None
    tool: Optional[str] = None
    prompt: Optional[str] = None
    output: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, filtering None values."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


class TraceStore:
    """Manages trace storage and retrieval."""
    
    def __init__(self, base_dir: str = "data/traces"):
        """Initialize trace store.
        
        Args:
            base_dir: Base directory for trace files
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _trace_file(self, chat_id: str) -> Path:
        """Get trace file path for a chat ID."""
        return self.base_dir / f"{chat_id}.jsonl"
    
    def record_event(self, event: TraceEvent) -> None:
        """Record a trace event.
        
        Args:
            event: The trace event to record
        """
        trace_file = self._trace_file(event.chat_id)
        
        with trace_file.open('a', encoding='utf-8') as f:
            json.dump(event.to_dict(), f, ensure_ascii=False)
            f.write('\n')
    
    def record_node_enter(
        self, 
        chat_id: str, 
        node: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record node entry event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.NODE_ENTER,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            node=node,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def record_node_exit(
        self,
        chat_id: str,
        node: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record node exit event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.NODE_EXIT,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            node=node,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def record_tool_call(
        self,
        chat_id: str,
        tool: str,
        prompt: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record tool call event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.TOOL_CALL,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            tool=tool,
            prompt=prompt,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def record_tool_result(
        self,
        chat_id: str,
        tool: str,
        output: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record tool result event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.TOOL_RESULT,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            tool=tool,
            output=output,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def record_llm_prompt(
        self,
        chat_id: str,
        prompt: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record LLM prompt event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.LLM_PROMPT,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            prompt=prompt,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def record_llm_output(
        self,
        chat_id: str,
        output: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record LLM output event."""
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=TraceEventType.LLM_OUTPUT,
            chat_id=chat_id,
            trace_id=trace_id,
            span_id=span_id,
            output=output,
            metadata=metadata or {}
        )
        self.record_event(event)
    
    def get_trace(self, chat_id: str) -> List[TraceEvent]:
        """Get all trace events for a chat ID.
        
        Args:
            chat_id: The chat ID to get traces for
            
        Returns:
            List of trace events in chronological order
        """
        trace_file = self._trace_file(chat_id)
        if not trace_file.exists():
            return []
        
        events = []
        with trace_file.open('r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line.strip())
                    # Reconstruct TraceEvent from dict
                    event = TraceEvent(
                        timestamp=data['timestamp'],
                        event_type=TraceEventType(data['event_type']),
                        chat_id=data['chat_id'],
                        trace_id=data.get('trace_id'),
                        span_id=data.get('span_id'),
                        node=data.get('node'),
                        tool=data.get('tool'),
                        prompt=data.get('prompt'),
                        output=data.get('output'),
                        metadata=data.get('metadata')
                    )
                    events.append(event)
        
        return events
    
    def get_llm_outputs(self, chat_id: str) -> Iterator[tuple[str, str]]:
        """Get LLM prompt/output pairs for replay.
        
        Args:
            chat_id: The chat ID to get outputs for
            
        Yields:
            Tuples of (prompt, output) for each LLM interaction
        """
        events = self.get_trace(chat_id)
        
        # Group prompt/output pairs
        pending_prompts = {}
        
        for event in events:
            if event.event_type == TraceEventType.LLM_PROMPT and event.prompt:
                # Use span_id as key to match prompts with outputs
                key = event.span_id or f"{event.node}_{event.timestamp}"
                pending_prompts[key] = event.prompt
            elif event.event_type == TraceEventType.LLM_OUTPUT and event.output:
                key = event.span_id or f"{event.node}_{event.timestamp}"
                if key in pending_prompts:
                    yield (pending_prompts[key], event.output)
                    del pending_prompts[key]
    
    def list_traces(self) -> List[str]:
        """List all available trace chat IDs."""
        if not self.base_dir.exists():
            return []
        
        chat_ids = []
        for trace_file in self.base_dir.glob("*.jsonl"):
            chat_ids.append(trace_file.stem)
        
        return sorted(chat_ids)
    
    def trace_exists(self, chat_id: str) -> bool:
        """Check if a trace exists for the given chat ID."""
        return self._trace_file(chat_id).exists()


# Global trace store instance
_trace_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    """Get the global trace store instance."""
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceStore()
    return _trace_store