"""Tests for replay functionality."""

import pytest
import tempfile
from pathlib import Path
from agentic_ai.memory.trace_store import TraceStore, TraceEvent, TraceEventType
from agentic_ai.llm.replay_llm import ReplayLLM
from langchain_core.messages import HumanMessage


def test_trace_store_round_trip():
    """Test storing and retrieving trace events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TraceStore(base_dir=tmpdir)
        
        # Record some events
        chat_id = "test_chat_123"
        store.record_node_enter(chat_id, "plan", trace_id="trace1", span_id="span1")
        store.record_llm_prompt(chat_id, "Test prompt", trace_id="trace1", span_id="span1")
        store.record_llm_output(chat_id, "Test output", trace_id="trace1", span_id="span1")
        store.record_node_exit(chat_id, "plan", trace_id="trace1", span_id="span1")
        
        # Retrieve events
        events = store.get_trace(chat_id)
        assert len(events) == 4
        
        # Check event types
        assert events[0].event_type == TraceEventType.NODE_ENTER
        assert events[1].event_type == TraceEventType.LLM_PROMPT
        assert events[2].event_type == TraceEventType.LLM_OUTPUT
        assert events[3].event_type == TraceEventType.NODE_EXIT
        
        # Check LLM outputs
        llm_outputs = list(store.get_llm_outputs(chat_id))
        assert len(llm_outputs) == 1
        assert llm_outputs[0] == ("Test prompt", "Test output")


def test_trace_store_multiple_chats():
    """Test handling multiple chat IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TraceStore(base_dir=tmpdir)
        
        # Record events for multiple chats
        store.record_node_enter("chat1", "plan")
        store.record_node_enter("chat2", "plan")
        
        # List traces
        traces = store.list_traces()
        assert len(traces) == 2
        assert "chat1" in traces
        assert "chat2" in traces
        
        # Check individual traces
        assert len(store.get_trace("chat1")) == 1
        assert len(store.get_trace("chat2")) == 1
        assert len(store.get_trace("nonexistent")) == 0


def test_replay_llm_basic():
    """Test basic ReplayLLM functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TraceStore(base_dir=tmpdir)
        
        # Create some recorded outputs
        chat_id = "replay_test"
        store.record_llm_prompt(chat_id, "What is 2+2?", span_id="span1")
        store.record_llm_output(chat_id, "2+2 equals 4", span_id="span1")
        store.record_llm_prompt(chat_id, "What is the capital of France?", span_id="span2")
        store.record_llm_output(chat_id, "The capital of France is Paris", span_id="span2")
        
        # Create ReplayLLM with custom trace store
        replay_llm = ReplayLLM(chat_id=chat_id, strict_mode=True)
        replay_llm._trace_store = store  # Override with test store
        replay_llm._recorded_outputs = list(store.get_llm_outputs(chat_id))
        replay_llm._output_index = 0
        
        # Test invocation
        messages = [HumanMessage(content="What is 2+2?")]
        result = replay_llm.invoke(messages)
        
        assert result.content == "2+2 equals 4"
        
        # Test second invocation
        messages = [HumanMessage(content="What is the capital of France?")]
        result = replay_llm.invoke(messages)
        
        assert result.content == "The capital of France is Paris"


def test_replay_llm_no_output():
    """Test ReplayLLM when no recorded output is available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TraceStore(base_dir=tmpdir)
        
        # Create ReplayLLM with no recorded outputs
        chat_id = "empty_chat"
        replay_llm = ReplayLLM(chat_id=chat_id, strict_mode=False)
        replay_llm._trace_store = store
        replay_llm._recorded_outputs = list(store.get_llm_outputs(chat_id))
        replay_llm._output_index = 0
        
        # Should return fallback message
        messages = [HumanMessage(content="Hello")]
        result = replay_llm.invoke(messages)
        
        assert "[REPLAY ERROR:" in result.content
        
        # Test strict mode
        replay_llm_strict = ReplayLLM(chat_id=chat_id, strict_mode=True)
        replay_llm_strict._trace_store = store
        replay_llm_strict._recorded_outputs = list(store.get_llm_outputs(chat_id))
        replay_llm_strict._output_index = 0
        
        with pytest.raises(ValueError, match="No recorded output found"):
            replay_llm_strict.invoke(messages)


def test_replay_llm_reset():
    """Test ReplayLLM reset functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TraceStore(base_dir=tmpdir)
        
        # Create recorded output
        chat_id = "reset_test"
        store.record_llm_prompt(chat_id, "Test prompt", span_id="span1")
        store.record_llm_output(chat_id, "Test output", span_id="span1")
        
        replay_llm = ReplayLLM(chat_id=chat_id)
        replay_llm._trace_store = store
        replay_llm._recorded_outputs = list(store.get_llm_outputs(chat_id))
        replay_llm._output_index = 0
        
        # Use the output
        messages = [HumanMessage(content="Test prompt")]
        result1 = replay_llm.invoke(messages)
        assert result1.content == "Test output"
        
        # Should have no more outputs
        assert replay_llm.get_remaining_outputs() == 0
        
        # Reset and try again
        replay_llm.reset()
        assert replay_llm.get_remaining_outputs() == 1
        
        result2 = replay_llm.invoke(messages)
        assert result2.content == "Test output"