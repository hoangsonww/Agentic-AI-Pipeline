.PHONY: setup run dev test format lint ingest demo eval
setup:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	cp -n .env.example .env || true

run:
	. .venv/bin/activate && uvicorn agentic_ai.app:app --reload --host $$(grep -E "^APP_HOST=" .env | cut -d= -f2 || echo 0.0.0.0) --port $$(grep -E "^APP_PORT=" .env | cut -d= -f2 || echo 8000)

dev: run

test:
	. .venv/bin/activate && pytest -q

format:
	. .venv/bin/activate && ruff check --select I --fix src tests && ruff format src tests

lint:
	. .venv/bin/activate && ruff check src tests && ruff format --check src tests

ingest:
	. .venv/bin/activate && python -m agentic_ai.cli ingest "./data/seed"

demo:
	. .venv/bin/activate && python -m agentic_ai.cli demo "Give me a competitive briefing on ACME Robotics and draft a short outreach email."

eval:
	. .venv/bin/activate && python -m tests.evals.runner --output eval_results.xml
