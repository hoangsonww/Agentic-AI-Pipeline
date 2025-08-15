@echo off
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist .env (
  copy .env.example .env
  echo Edit .env with your keys before running again.
  exit /b 1
)

if not exist corpus mkdir corpus
if not exist .session_memory mkdir .session_memory

py app.py
