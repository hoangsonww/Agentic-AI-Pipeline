set dotenv-load := true

venv := ".venv"

alias r := run
alias t := test

setup:
\tpython -m venv {{venv}}
\t. {{venv}}/bin/activate && pip install -U pip && pip install -r requirements.txt
\t@[ -f .env ] || cp .env.example .env

run:
\t. {{venv}}/bin/activate && uvicorn agentic_ai.app:app --reload --host {{env_var("APP_HOST","0.0.0.0")}} --port {{env_var("APP_PORT","8000")}}

ingest:
\t. {{venv}}/bin/activate && python -m agentic_ai.cli ingest "./data/seed"

demo *ARGS:
\t. {{venv}}/bin/activate && python -m agentic_ai.cli demo {{join(ARGS, " ")}}

test:
\t. {{venv}}/bin/activate && pytest -q

fmt:
\t. {{venv}}/bin/activate && ruff check --select I --fix src tests && ruff format src tests

lint:
\t. {{venv}}/bin/activate && ruff check src tests && ruff format --check src tests

docker-build:
\tdocker build -t agentic-ai:dev .

docker-run:
\tIMAGE=agentic-ai:dev bash scripts/run_docker.sh

compose-up:
\tdocker compose up --build -d

compose-down:
\tdocker compose down -v
