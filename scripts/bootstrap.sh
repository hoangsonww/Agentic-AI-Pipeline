#!/usr/bin/env bash
set -euo pipefail
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
. .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "✅ Python env ready."
