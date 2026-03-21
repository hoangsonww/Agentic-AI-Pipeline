# syntax=docker/dockerfile:1.7
# =============================================================================
# Stage 1: Builder — install deps into a virtual env
# =============================================================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# System deps needed to compile lxml, trafilatura, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# =============================================================================
# Stage 2: Runtime — lean image with only what we need
# =============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Runtime system deps (libxml2 needed by lxml at runtime; curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-built virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY src/          /app/src/
COPY web/          /app/web/
COPY mcp/          /app/mcp/
COPY pyproject.toml /app/pyproject.toml
COPY requirements.txt /app/requirements.txt
COPY .env.example  /app/.env.example

# Copy sub-pipelines (optional — built as part of monorepo)
COPY Agentic-Coding-Pipeline/ /app/Agentic-Coding-Pipeline/
COPY Agentic-RAG-Pipeline/    /app/Agentic-RAG-Pipeline/

# Create directories for runtime data
RUN mkdir -p /app/.logs /app/.chroma /app/.sqlite \
             /app/data/seed /app/data/agent_output /app/data/emails

# Copy seed data
COPY data/seed/ /app/data/seed/

# Non-root user with writable home (ChromaDB caches ONNX model in ~/.cache)
RUN groupadd --gid 1001 appuser && \
    useradd  --uid 1001 --gid appuser --home-dir /home/appuser --create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "agentic_ai.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
