set dotenv-load := true

venv := ".venv"

alias r := run
alias t := test

setup:
	python -m venv {{venv}}
	. {{venv}}/bin/activate && pip install -U pip && pip install -r requirements.txt
	@[ -f .env ] || cp .env.example .env

run:
	. {{venv}}/bin/activate && PYTHONPATH=src uvicorn agentic_ai.app:app --reload --host {{env_var_or_default("APP_HOST","0.0.0.0")}} --port {{env_var_or_default("APP_PORT","8000")}}

ingest:
	. {{venv}}/bin/activate && PYTHONPATH=src python -m agentic_ai.cli ingest "./data/seed"

demo *ARGS:
	. {{venv}}/bin/activate && PYTHONPATH=src python -m agentic_ai.cli demo {{ARGS}}

test:
	. {{venv}}/bin/activate && PYTHONPATH=src pytest -q --tb=short

fmt:
	. {{venv}}/bin/activate && ruff check --select I --fix src tests mcp && ruff format src tests mcp

lint:
	. {{venv}}/bin/activate && ruff check src tests mcp && ruff format --check src tests mcp

health:
	@curl -fsS http://localhost:${APP_PORT:-8000}/health && echo " OK"

docker-build:
	docker build -t agentic-ai:latest .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env agentic-ai:latest

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v
