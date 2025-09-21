"""
Lightweight tracing system for LangGraph agent runs.

Captures node transitions, tool I/O, timings, and state changes as JSONL events.
Designed for debugging, reproducibility, and evaluation.
"""
from __future__ import annotations

import json
import time
import uuid
import hashlib
import os
import random
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from ..config import settings


@dataclass 
class TraceEvent:
    """Single trace event in JSONL format"""
    event_type: str
    timestamp: float
    node_name: str
    event_id: str
    chat_id: str
    run_id: str
    data: Dict[str, Any]
    duration_ms: Optional[float] = None


class RunTracer:
    """Context manager for tracing a single agent run"""
    
    def __init__(self, chat_id: str, run_id: Optional[str] = None):
        self.chat_id = chat_id
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.trace_dir = Path("data/traces") / chat_id
        self.trace_file = self.trace_dir / f"{self.run_id}.jsonl"
        self.start_time = time.time()
        self.active_spans: Dict[str, float] = {}
        
        # Ensure trace directory exists
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        
    def __enter__(self):
        self._emit_event("run_start", "root", {
            "chat_id": self.chat_id,
            "run_id": self.run_id,
            "start_time": datetime.now(timezone.utc).isoformat()
        })
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        total_duration = (time.time() - self.start_time) * 1000
        self._emit_event("run_end", "root", {
            "total_duration_ms": total_duration,
            "error": str(exc_val) if exc_val else None
        })
    
    def _emit_event(self, event_type: str, node_name: str, data: Dict[str, Any], duration_ms: Optional[float] = None):
        """Write a single event to the JSONL trace file"""
        event = TraceEvent(
            event_type=event_type,
            timestamp=time.time(),
            node_name=node_name,
            event_id=str(uuid.uuid4())[:8],
            chat_id=self.chat_id,
            run_id=self.run_id,
            data=self._redact_sensitive_data(data),
            duration_ms=duration_ms
        )
        
        with open(self.trace_file, "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from trace data"""
        redacted = data.copy()
        
        # Redact common sensitive patterns
        sensitive_keys = ["api_key", "token", "password", "authorization", "cookie"]
        for key in list(redacted.keys()):
            if any(pattern in key.lower() for pattern in sensitive_keys):
                redacted[key] = "[REDACTED]"
        
        # Truncate large content
        max_content_length = getattr(settings, 'TRACE_MAX_CONTENT_LENGTH', 2000)
        for key, value in redacted.items():
            if isinstance(value, str) and len(value) > max_content_length:
                redacted[key] = value[:max_content_length] + f"...[TRUNCATED:{len(value)} chars]"
                
        return redacted
    
    @contextmanager
    def span(self, node_name: str, operation: str = "execute"):
        """Context manager for timing node operations"""
        span_id = f"{node_name}_{operation}"
        start_time = time.time()
        self.active_spans[span_id] = start_time
        
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.active_spans.pop(span_id, None)
    
    def log_node_start(self, node_name: str, input_data: Dict[str, Any]):
        """Log the start of a node execution"""
        self._emit_event("node_start", node_name, {
            "input": input_data,
            "operation": "execute"
        })
    
    def log_node_end(self, node_name: str, output_data: Dict[str, Any], duration_ms: float):
        """Log the end of a node execution"""
        self._emit_event("node_end", node_name, {
            "output": output_data
        }, duration_ms=duration_ms)
    
    def log_tool_request(self, tool_name: str, args: Dict[str, Any]):
        """Log a tool call request"""
        args_hash = hashlib.md5(json.dumps(args, sort_keys=True).encode()).hexdigest()[:8]
        self._emit_event("tool_request", "tools", {
            "tool_name": tool_name,
            "args": args,
            "args_hash": args_hash
        })
    
    def log_tool_response(self, tool_name: str, result: Any, duration_ms: float, error: Optional[str] = None):
        """Log a tool call response"""
        result_hash = None
        if result is not None:
            result_str = str(result) if not isinstance(result, str) else result
            result_hash = hashlib.md5(result_str.encode()).hexdigest()[:8]
            
        self._emit_event("tool_response", "tools", {
            "tool_name": tool_name,
            "result": result,
            "result_hash": result_hash,
            "error": error
        }, duration_ms=duration_ms)
    
    def log_state_transition(self, from_state: str, to_state: str, data: Dict[str, Any] = None):
        """Log state transitions in the agent"""
        self._emit_event("state_transition", "graph", {
            "from_state": from_state,
            "to_state": to_state,
            "transition_data": data or {}
        })
    
    def log_llm_call(self, provider: str, model: str, input_tokens: Optional[int] = None, 
                     output_tokens: Optional[int] = None, duration_ms: Optional[float] = None):
        """Log LLM API calls with token counts"""
        self._emit_event("llm_call", "llm", {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }, duration_ms=duration_ms)


# Global tracer instance for the current run
_current_tracer: Optional[RunTracer] = None


def get_current_tracer() -> Optional[RunTracer]:
    """Get the currently active tracer"""
    return _current_tracer


def set_current_tracer(tracer: Optional[RunTracer]):
    """Set the current tracer (used by context managers)"""
    global _current_tracer
    _current_tracer = tracer


@contextmanager
def trace_run(chat_id: str, run_id: Optional[str] = None):
    """Context manager to enable tracing for an agent run"""
    # Check both settings and environment variable
    enable_tracing = getattr(settings, 'ENABLE_TRACING', False) or os.getenv('ENABLE_TRACING', '').lower() == 'true'
    
    if not enable_tracing:
        yield None
        return
        
    tracer = RunTracer(chat_id, run_id)
    old_tracer = get_current_tracer()
    
    try:
        set_current_tracer(tracer)
        with tracer:
            yield tracer
    finally:
        set_current_tracer(old_tracer)


def read_trace(trace_path: Union[str, Path]) -> List[TraceEvent]:
    """Read and parse a trace file"""
    events = []
    with open(trace_path, 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            events.append(TraceEvent(**data))
    return events


def seed_randomness(seed: Optional[Union[str, int]] = None):
    """Seed random number generators for reproducible runs"""
    if seed is None:
        return
    
    # Convert string seeds to integers
    if isinstance(seed, str):
        seed = hash(seed) % (2**32)
    
    # Seed Python's random module
    random.seed(seed)
    
    # Seed numpy if available
    try:
        import numpy as np
        np.random.seed(seed % (2**32))
    except ImportError:
        pass
    
    # Set environment variable for other libraries
    os.environ['PYTHONHASHSEED'] = str(seed)


def create_reproducible_run_id(chat_id: str, user_message: str, seed: Optional[str] = None) -> str:
    """Create a deterministic run ID for reproducible runs"""
    if seed:
        # Use seed to create deterministic run ID
        content = f"{chat_id}:{user_message}:{seed}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    else:
        # Use random run ID
        return str(uuid.uuid4())[:8]