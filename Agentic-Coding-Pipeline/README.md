# Agentic Coding Pipeline

This module provides an autonomous coding workflow built from multiple cooperating
agents. The pipeline contains coding agents that propose code changes, testing
agents that verify correctness, and quality assurance agents that ensure style
and code health.

## Components

- **Coding agents** generate or modify code using LLMs.
- **Testing agents** run project test suites and report failures.
- **QA/QC agents** perform static analysis and style checks.
- **Orchestrator** coordinates agents and repeats iterations until all checks
  pass or a maximum number of attempts is reached.

The pipeline is intentionally modular so additional agents (documentation,
security, deployment, etc.) can be added easily.

## Usage

```bash
python -m agentic_coding_pipeline.run "Add feature X"
```

An `OPENAI_API_KEY` environment variable is required for coding agents that
leverage OpenAI models. Testing and QA agents rely on local tooling such as
`pytest` and `ruff`.
```
