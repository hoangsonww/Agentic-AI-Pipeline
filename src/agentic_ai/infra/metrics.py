"""OpenTelemetry metrics setup for agentic AI pipeline."""

from __future__ import annotations

import os
from typing import Optional
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
try:
    from opentelemetry.semantic_conventions.resource import ResourceAttributes
    SEMANTIC_CONVENTIONS_AVAILABLE = True
except ImportError:
    # Fallback constants if semantic conventions not available
    SEMANTIC_CONVENTIONS_AVAILABLE = False
    class ResourceAttributes:
        SERVICE_NAME = "service.name"
        SERVICE_VERSION = "service.version"
        SERVICE_NAMESPACE = "service.namespace"

# Global meter instance
_meter: Optional[metrics.Meter] = None
_initialized = False

# Metric instruments
_token_counter: Optional[metrics.Counter] = None
_latency_histogram: Optional[metrics.Histogram] = None
_cost_counter: Optional[metrics.Counter] = None
_tool_counter: Optional[metrics.Counter] = None


def init_metrics(
    service_name: str = "agentic-ai-pipeline",
    service_version: str = "0.3.0",
) -> metrics.Meter:
    """Initialize OpenTelemetry metrics.
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        
    Returns:
        Configured meter instance
    """
    global _meter, _initialized, _token_counter, _latency_histogram, _cost_counter, _tool_counter
    
    if _initialized:
        return _meter
    
    # Create resource
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.SERVICE_NAMESPACE: "agentic-ai",
    })
    
    # Set up meter provider
    provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(provider)
    
    # Create meter
    _meter = metrics.get_meter(__name__)
    
    # Create metric instruments
    _token_counter = _meter.create_counter(
        name="agent_tokens_total",
        description="Total number of tokens processed",
        unit="1",
    )
    
    _latency_histogram = _meter.create_histogram(
        name="agent_operation_duration",
        description="Duration of agent operations",
        unit="ms",
    )
    
    _cost_counter = _meter.create_counter(
        name="agent_cost_total",
        description="Total cost in USD",
        unit="usd",
    )
    
    _tool_counter = _meter.create_counter(
        name="agent_tool_calls_total",
        description="Total number of tool calls",
        unit="1",
    )
    
    _initialized = True
    return _meter


def get_meter() -> metrics.Meter:
    """Get the global meter instance, initializing if needed."""
    if not _initialized:
        return init_metrics()
    return _meter


def record_tokens(count: int, token_type: str, provider: str, model: str):
    """Record token usage."""
    if _token_counter:
        _token_counter.add(count, {
            "token_type": token_type,
            "provider": provider,
            "model": model,
        })


def record_latency(duration_ms: float, operation: str, provider: Optional[str] = None):
    """Record operation latency."""
    if _latency_histogram:
        attributes = {"operation": operation}
        if provider:
            attributes["provider"] = provider
        _latency_histogram.record(duration_ms, attributes)


def record_cost(cost_usd: float, provider: str, model: str):
    """Record operation cost."""
    if _cost_counter:
        _cost_counter.add(cost_usd, {
            "provider": provider,
            "model": model,
        })


def record_tool_call(tool_name: str, success: bool):
    """Record tool call."""
    if _tool_counter:
        _tool_counter.add(1, {
            "tool": tool_name,
            "success": str(success).lower(),
        })