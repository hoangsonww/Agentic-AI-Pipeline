from __future__ import annotations
import time
from typing import List
from langchain.tools import BaseTool
from langgraph.prebuilt import ToolNode
from ..tools.webtools import WebSearch, WebFetch
from ..tools.ops import Calculator, FileWrite, Emailer
from ..tools.knowledge import KbSearch, KbAdd
from ..infra.tracing import get_tracer, current_trace_id, current_span_id
from ..infra.metrics import record_latency, record_tool_call
from ..memory.trace_store import get_trace_store
from ..infra.logging import logger


class TracedToolNode:
    """Wrapper around ToolNode that adds tracing."""
    
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools
        self.tool_node = ToolNode(tools)
        
    def __call__(self, state):
        """Execute tools with tracing."""
        tracer = get_tracer()
        trace_store = get_trace_store()
        chat_id = state.get("chat_id", "unknown")
        
        with tracer.start_as_current_span("agent.tools") as span:
            start_time = time.time()
            span.set_attribute("chat_id", chat_id)
            span.set_attribute("node", "tools")
            
            # Record node entry
            trace_store.record_node_enter(
                chat_id=chat_id,
                node="tools",
                trace_id=current_trace_id(),
                span_id=current_span_id()
            )
            
            try:
                # Get the last message which should contain tool calls
                last_message = state["messages"][-1] if state["messages"] else None
                tool_calls = []
                
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    tool_calls = last_message.tool_calls
                    span.set_attribute("tool_calls_count", len(tool_calls))
                    
                    # Record each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('args', {})
                        
                        # Record tool call with tracing
                        with tracer.start_as_current_span(f"agent.tools.{tool_name}") as tool_span:
                            tool_start = time.time()
                            tool_span.set_attribute("chat_id", chat_id)
                            tool_span.set_attribute("tool", tool_name)
                            tool_span.set_attribute("tool_args", str(tool_args))
                            
                            # Record tool call event
                            trace_store.record_tool_call(
                                chat_id=chat_id,
                                tool=tool_name,
                                prompt=str(tool_args),
                                trace_id=current_trace_id(),
                                span_id=current_span_id(),
                                metadata={"args": tool_args}
                            )
                
                # Execute the original tool node
                result_state = self.tool_node(state)
                
                # Record results and timing for completed tool calls
                if tool_calls:
                    # Get the tool result messages (should be the new messages added)
                    new_messages = result_state["messages"][len(state["messages"]):]
                    
                    for i, tool_call in enumerate(tool_calls):
                        tool_name = tool_call.get('name', 'unknown')
                        tool_duration_ms = (time.time() - start_time) * 1000 / len(tool_calls)
                        
                        # Record metrics
                        record_latency(tool_duration_ms, f"tools.{tool_name}")
                        record_tool_call(tool_name, True)  # Assume success if no exception
                        
                        # Record tool result if available
                        if i < len(new_messages):
                            result_content = getattr(new_messages[i], 'content', '')
                            trace_store.record_tool_result(
                                chat_id=chat_id,
                                tool=tool_name,
                                output=result_content,
                                trace_id=current_trace_id(),
                                span_id=current_span_id(),
                                metadata={"latency_ms": tool_duration_ms}
                            )
                
                # Record overall timing and success
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("success", True)
                record_latency(duration_ms, "agent.tools")
                
                # Record node exit
                trace_store.record_node_exit(
                    chat_id=chat_id,
                    node="tools",
                    trace_id=current_trace_id(),
                    span_id=current_span_id(),
                    metadata={"latency_ms": duration_ms, "tool_calls_count": len(tool_calls)}
                )
                
                return result_state
                
            except Exception as e:
                # Record failed tool calls
                if 'tool_calls' in locals():
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        record_tool_call(tool_name, False)
                
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error in tools execution: {e}")
                raise


def registry() -> List[BaseTool]:
    return [
        WebSearch(),
        WebFetch(),
        KbSearch(),
        KbAdd(),
        Calculator(),
        FileWrite(),
        Emailer()
    ]
