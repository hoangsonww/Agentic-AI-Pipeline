# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=on
WORKDIR /app

# System deps for lxml/trafilatura
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

# Install deps early for caching
COPY requirements.txt /app/requirements.txt
RUN python -m pip install -U pip && pip install -r requirements.txt

# Copy source
COPY src /app/src
COPY web /app/web
COPY .env.example /app/.env.example
COPY pyproject.toml /app/pyproject.toml 2>/dev/null || true

ENV APP_HOST=0.0.0.0 APP_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/new_chat || exit 1

CMD ["python","-m","uvicorn","agentic_ai.app:app","--host","0.0.0.0","--port","8000"]
