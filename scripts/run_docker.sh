#!/usr/bin/env bash
set -euo pipefail
IMAGE="${IMAGE:-agentic-ai:dev}"
docker build -t "$IMAGE" .
docker run --rm -it -p 8000:8000 \
  --env-file .env \
  -e CHROMA_DIR=/data/chroma -e SQLITE_PATH=/data/sqlite/agent.db \
  -v "$(pwd)/data/seed:/app/data/seed:ro" \
  -v "$(pwd)/data/agent_output:/app/data/agent_output" \
  -v "$(pwd)/data/emails:/app/data/emails" \
  -v "$(pwd)/.logs:/app/.logs" \
  "$IMAGE"
