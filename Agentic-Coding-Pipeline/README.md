# Agentic Coding Pipeline

An autonomous, multi-agent workflow that iteratively edits a codebase until LLM-generated tests and reviews pass.

## Overview

This pipeline coordinates several specialized agents backed by pluggable LLM providers:

- **Coding agents** synthesize or refine patches. By default both OpenAI and Claude models collaborate to produce code.
- **Formatting agents** run local tooling (e.g. `ruff --fix`) to keep style consistent.
- **Testing agents** ask an LLM (default Claude) to draft pytest suites and execute them locally.
- **QA/QC agents** perform LLM-based code review (default Gemini) to ensure style and correctness.
- **Orchestrator** loops until all checks succeed or a retry limit is reached.

The design is modular so additional roles (documentation, security, deployment, etc.) can be plugged in without altering the core loop.

## MCP Server Integration

The pipeline registers with the shared [`mcp`](../mcp) package. A central `MCPServer` allows any of the project pipelines (research outreach, RAG, or coding) to dispatch tasks through a common FastAPI server that also exposes web search, browsing tools and direct LLM access.

## Running the Pipeline

```bash
cd Agentic-Coding-Pipeline
python run.py "Add feature X"
```

The default configuration uses OpenAI and Claude for coding, formats code with Ruff, generates tests with Claude and reviews with Gemini. Set the corresponding API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) so agents can call each provider. Local tooling such as `pytest` is used to run the tests emitted by the LLM.

## Extending

Modify `pipeline.py` to add new agent steps or alter the iteration logic. New tasks can be exposed to the MCP server by registering them in `run.py`.

## Tests

Run the built-in checks to verify that the pipeline operates correctly:

```bash
ruff check .
pytest tests/test_pipeline.py
```
