#!/usr/bin/env bash
set -euo pipefail
. .venv/bin/activate
export APP_HOST="${APP_HOST:-0.0.0.0}"
export APP_PORT="${APP_PORT:-8000}"
echo "▶ Starting API on $APP_HOST:$APP_PORT"
exec uvicorn agentic_ai.app:app --reload --host "$APP_HOST" --port "$APP_PORT"
