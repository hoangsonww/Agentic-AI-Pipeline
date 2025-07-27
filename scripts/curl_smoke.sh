#!/usr/bin/env bash
set -euo pipefail
HOST="${1:-http://127.0.0.1:8000}"
curl -fsS "$HOST/api/new_chat"
curl -fsS -X POST "$HOST/api/ingest" -H "Content-Type: application/json" -d text:kb from script
