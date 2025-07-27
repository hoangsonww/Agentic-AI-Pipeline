#!/usr/bin/env bash
set -euo pipefail
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
