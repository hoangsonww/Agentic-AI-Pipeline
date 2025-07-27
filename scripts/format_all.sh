#!/usr/bin/env bash
set -euo pipefail
if [ -d ".venv" ]; then
  . .venv/bin/activate || true
fi
echo "▶ Ruff (Python)"
ruff check --select I --fix src tests || true
ruff format src tests || true
if command -v npx >/dev/null 2>&1; then
  echo "▶ Prettier (web & TS)"
  npx prettier -w "web/**/*.{js,css,json}" "clients/ts/**/*.{ts,tsx,json}" || true
fi
echo "✅ Formatting done."
