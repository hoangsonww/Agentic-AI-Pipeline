"""Tests for tracing infrastructure."""

import pytest
from agentic_ai.infra.tracing import init_tracing, get_tracer, create_span


def test_init_tracing():
    """Test tracing initialization."""
    tracer = init_tracing(service_name="test-service")
    assert tracer is not None
    
    # Should return same instance on subsequent calls
    tracer2 = init_tracing()
    assert tracer is tracer2


def test_get_tracer():
    """Test tracer retrieval."""
    tracer = get_tracer()
    assert tracer is not None


def test_create_span():
    """Test span creation."""
    with create_span("test.operation", test_attr="value") as span:
        assert span is not None
        assert span.is_recording()


def test_current_trace_functions():
    """Test current trace/span ID functions."""
    from agentic_ai.infra.tracing import current_trace_id, current_span_id
    
    # Without active span, should return None
    assert current_trace_id() is None
    assert current_span_id() is None
    
    # With active span, should return IDs
    with create_span("test.span") as span:
        trace_id = current_trace_id()
        span_id = current_span_id()
        
        # Should be hex strings of correct length
        if trace_id:
            assert len(trace_id) == 32
            assert all(c in '0123456789abcdef' for c in trace_id)
        
        if span_id:
            assert len(span_id) == 16
            assert all(c in '0123456789abcdef' for c in span_id)