#!/usr/bin/env bash
set -euo pipefail
. .venv/bin/activate
python -m agentic_ai.cli ingest "./data/seed" >/dev/null
python -m agentic_ai.cli demo "Give me a compact briefing on AMR vendors with citations"
