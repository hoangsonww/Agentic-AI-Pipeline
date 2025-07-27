#!/usr/bin/env bash
set -euo pipefail
pushd clients/ts >/dev/null
if command -v corepack >/dev/null 2>&1; then
  corepack enable || true
fi
npm install
npm run build
echo "✅ TS client built. Run: BASE_URL=http://127.0.0.1:8000 npm run demo"
popd >/dev/null
