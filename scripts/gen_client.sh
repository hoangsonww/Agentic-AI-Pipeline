#!/usr/bin/env bash
set -euo pipefail
python scripts/export_openapi.py
if ! command -v openapi-python-client >/dev/null 2>&1; then
  echo "openapi-python-client not found. Install with: pip install openapi-python-client"
  exit 1
fi
rm -rf clients/python
openapi-python-client generate --path openapi.json --meta none --custom-template-path "" --config /dev/null --output clients/python
echo "Client generated under clients/python"
