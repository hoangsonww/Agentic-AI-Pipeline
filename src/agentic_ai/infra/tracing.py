"""OpenTelemetry tracing setup for agentic AI pipeline."""

from __future__ import annotations

import os
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
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

# Try to import optional components
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FASTAPI_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    FASTAPI_INSTRUMENTATION_AVAILABLE = False

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_initialized = False


def init_tracing(
    service_name: str = "agentic-ai-pipeline",
    service_version: str = "0.3.0",
    otlp_endpoint: Optional[str] = None,
    sample_rate: float = 1.0,
) -> trace.Tracer:
    """Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (defaults to localhost:4317)
        sample_rate: Sampling rate (0.0 to 1.0)
        
    Returns:
        Configured tracer instance
    """
    global _tracer, _initialized
    
    if _initialized:
        return _tracer
    
    # Create resource with service information
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.SERVICE_NAMESPACE: "agentic-ai",
    })
    
    # Set up tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    # Configure OTLP exporter if endpoint is provided and available
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    if otlp_endpoint and OTLP_AVAILABLE:
        try:
            exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True,  # For local development
            )
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
        except Exception as e:
            # If OTLP export fails, continue without it (for development)
            print(f"Warning: Failed to initialize OTLP exporter: {e}")
    elif otlp_endpoint and not OTLP_AVAILABLE:
        print("Warning: OTLP endpoint specified but OTLP exporter not available")
    
    # Create tracer
    _tracer = trace.get_tracer(__name__)
    _initialized = True
    
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance, initializing if needed."""
    if not _initialized:
        return init_tracing()
    return _tracer


def instrument_fastapi(app):
    """Instrument FastAPI app with OpenTelemetry."""
    if FASTAPI_INSTRUMENTATION_AVAILABLE:
        FastAPIInstrumentor.instrument_app(app)
    else:
        print("Warning: FastAPI instrumentation not available")
    return app


def create_span(name: str, **attributes):
    """Create a new span with the given name and attributes."""
    tracer = get_tracer()
    span = tracer.start_span(name)
    
    # Add attributes to span
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, str(value))
    
    return span


def current_trace_id() -> Optional[str]:
    """Get the current trace ID as a hex string."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, '032x')
    return None


def current_span_id() -> Optional[str]:
    """Get the current span ID as a hex string."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, '016x')
    return None