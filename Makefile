.PHONY: setup run dev test format lint ingest demo health docker-build docker-run compose-up compose-down

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	@[ -f .env ] || cp .env.example .env

run:
	. .venv/bin/activate && PYTHONPATH=src uvicorn agentic_ai.app:app --reload \
		--host $$(grep -E "^APP_HOST=" .env 2>/dev/null | cut -d= -f2 || echo 0.0.0.0) \
		--port $$(grep -E "^APP_PORT=" .env 2>/dev/null | cut -d= -f2 || echo 8000)

dev: run

test:
	. .venv/bin/activate && PYTHONPATH=src pytest -q --tb=short

format:
	. .venv/bin/activate && ruff check --select I --fix src tests mcp && ruff format src tests mcp

lint:
	. .venv/bin/activate && ruff check src tests mcp && ruff format --check src tests mcp

ingest:
	. .venv/bin/activate && PYTHONPATH=src python -m agentic_ai.cli ingest "./data/seed"

demo:
	. .venv/bin/activate && PYTHONPATH=src python -m agentic_ai.cli demo "Give me a competitive briefing on ACME Robotics and draft a short outreach email."

health:
	@curl -fsS http://localhost:$${APP_PORT:-8000}/health && echo " OK" || echo " FAIL"

docker-build:
	docker build -t agentic-ai:latest .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env agentic-ai:latest

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v
