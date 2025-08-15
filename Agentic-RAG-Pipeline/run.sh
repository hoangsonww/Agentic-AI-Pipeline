#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "No .env found. Copying .env.example -> .env"
  cp .env.example .env
  echo "Edit .env with your keys before running again."
  exit 1
fi

mkdir -p corpus
mkdir -p .session_memory

python app.py
