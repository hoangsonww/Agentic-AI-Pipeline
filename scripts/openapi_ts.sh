#!/usr/bin/env bash
set -euo pipefail
python scripts/export_openapi.py
if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node.js/npm first."; exit 1
fi
npx openapi-typescript openapi.json -o clients/ts/src/openapi.types.ts
echo "✅ Wrote clients/ts/src/openapi.types.ts"
