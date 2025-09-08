# Agentic Coding Pipeline

An autonomous, multi-agent workflow that iteratively edits a codebase until tests and style checks pass.

## Overview

This pipeline coordinates several specialized agents:

- **Coding agents** propose or modify patches using LLMs.
- **Testing agents** execute the project's test suite and surface failures.
- **QA/QC agents** run formatters and static analysis like `ruff`.
- **Orchestrator** loops until all checks succeed or a retry limit is reached.

The design is modular so additional roles (documentation, security, deployment, etc.) can be plugged in without altering the core loop.

## MCP Server Integration

The pipeline registers with the shared [`mcp`](../mcp) package. A central `PipelineRegistry` allows any of the project pipelines (research outreach, RAG, or coding) to dispatch tasks through a common FastAPI server that also exposes web search and browsing tools.

## Running the Pipeline

```bash
cd Agentic-Coding-Pipeline
python run.py "Add feature X"
```

Set `OPENAI_API_KEY` so coding agents can call LLMs. Local tooling such as `pytest` and `ruff` is used for testing and quality checks.

## Extending

Modify `pipeline.py` to add new agent steps or alter the iteration logic. New tasks can be exposed to the MCP server by registering them in `run.py`.

## Tests

Run the built-in checks to verify that the pipeline operates correctly:

```bash
ruff check .
pytest tests/test_pipeline.py
```
