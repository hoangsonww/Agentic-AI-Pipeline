#!/usr/bin/env bash
set -euo pipefail
export APP_HOST="${APP_HOST:-0.0.0.0}"
export APP_PORT="${APP_PORT:-8000}"
uvicorn agentic_ai.app:app --reload --host "$APP_HOST" --port "$APP_PORT"
