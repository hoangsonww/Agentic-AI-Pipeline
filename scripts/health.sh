#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://127.0.0.1:8000}"
echo "Pinging $BASE_URL ..."
curl -fsS "$BASE_URL/api/new_chat" && echo -e "\n✅ OK" || (echo "❌ Failed"; exit 1)
