# RunLedger integration notes

This PR adds a small RunLedger suite under `evals/runledger` configured to run in replay mode (no live calls).

The included `agent/agent.py` is a thin adapter that runs this repo's core chat flow in a deterministic way (no API keys, no network). It uses:

- the repo's chat graph (`src/agentic_ai/graph.py` via `run_chat`)
- a deterministic stub model (so behavior is repeatable)
- RunLedger tool replay (tool calls are emitted over JSONL and satisfied by the cassette)

## Run locally

```bash
runledger run evals/runledger --mode replay --baseline baselines/runledger-demo.json
```

## Potential entrypoints in this repo

### Core chat entrypoint (suggested by maintainer)

- `src/agentic_ai/graph.py` via `run_chat` (used by `src/agentic_ai/app.py` and `src/agentic_ai/cli.py`)

### Python Poetry scripts (from `pyproject.toml`)

- `agentic-ai` = `agentic_ai.cli:main`

## Next steps (optional)

If you want this to exercise the real model/tools instead of a stubbed model:

1) Update `evals/runledger/agent/agent.py` to remove the stubbed model wiring.
2) Run once in `--mode record` to capture a cassette.
3) Run `--mode replay` in CI as a deterministic regression check.
