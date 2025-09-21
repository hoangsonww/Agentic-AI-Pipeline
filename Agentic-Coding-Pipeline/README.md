# Agentic Coding Pipeline (with Multi-LLM Pair Programming)

An end-to-end, production-ready **agentic coding** loop that composes, formats, tests, and reviews code until quality gates pass.
It orchestrates **specialized LLM agents**, **local tooling**, and **git-friendly utilities** so you can ship reliable patches on autopilot.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT%20Coders-412991?logo=openai&logoColor=white)](#)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude%20Coders-18181B?logo=apache&logoColor=white)](#)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Review-4285F4?logo=google&logoColor=white)](#)
[![Pytest](https://img.shields.io/badge/Pytest-Test%20Execution-0A9EDC?logo=pytest&logoColor=white)](#)
[![Ruff](https://img.shields.io/badge/Ruff-Formatting-000000?logo=ruff&logoColor=white)](#)
[![Git](https://img.shields.io/badge/Git-Patch%20Workflows-F05032?logo=git&logoColor=white)](#)
[![CLI](https://img.shields.io/badge/CLI-Argparse-4EAA25?logo=gnu-bash&logoColor=white)](#)
[![Poetry](https://img.shields.io/badge/Poetry-Env%20Mgmt-60A5FA?logo=poetry&logoColor=white)](#)
[![Makefile](https://img.shields.io/badge/Makefile-Tasks-000000?logo=gnu&logoColor=white)](#)
[![Automation](https://img.shields.io/badge/Automation-Iterative%20Loop-FF9800?logo=robot&logoColor=white)](#)
[![Quality](https://img.shields.io/badge/Quality-QA%20%2B%20Testing-4C1?logo=checkmarx&logoColor=white)](#)
[![Open%20Source](https://img.shields.io/badge/Open%20Source-Contributions%20Welcome-FF5722?logo=open-source-initiative&logoColor=white)](#)

---

## Contents

* [At a glance](#at-a-glance)
* [Architecture](#architecture)
* [Operational timeline](#operational-timeline)
* [Prerequisites](#prerequisites)
* [Quickstart](#quickstart)
* [Configuration reference](#configuration-reference)
* [Run](#run)
* [State contract](#state-contract)
* [Project structure](#project-structure)
* [Agents (roles & prompts)](#agents-roles--prompts)
* [Prompt reference](#prompt-reference)
* [Test synthesis & execution](#test-synthesis--execution)
* [Formatting & patch hygiene](#formatting--patch-hygiene)
* [Tooling & integration patterns](#tooling--integration-patterns)
* [MCP integration](#mcp-integration)
* [Extending & customization](#extending--customization)
* [Operations & observability](#operations--observability)
* [Quality control & failure handling](#quality-control--failure-handling)
* [Troubleshooting](#troubleshooting)
* [FAQ](#faq)

---

## At a glance

* **Multi-LLM coding pair** – OpenAI + Claude coders collaborate and hand off state between iterations.【F:Agentic-Coding-Pipeline/run.py†L21-L29】
* **Autonomous refinement loop** – The orchestrator keeps iterating until formatting, tests, and QA all succeed or retries are exhausted.【F:Agentic-Coding-Pipeline/pipeline.py†L21-L55】
* **Tool-backed quality gates** – Ruff auto-fixes style, pytest executes LLM-authored suites, and Gemini reviews the diff before completion.【F:Agentic-Coding-Pipeline/agents/formatting.py†L17-L26】【F:Agentic-Coding-Pipeline/agents/testing.py†L26-L42】【F:Agentic-Coding-Pipeline/agents/qa.py†L23-L33】
* **Git-friendly helpers** to commit generated patches directly from agents when desired.【F:Agentic-Coding-Pipeline/tools/git.py†L10-L14】
* **Drop-in modularity** – swap models or add agents without rewriting the orchestration contract thanks to a shared `Agent` protocol.【F:Agentic-Coding-Pipeline/agents/base.py†L9-L26】
* **Regression tests** – lightweight unit tests validate orchestration behaviour, providing a safety net for custom agents.【F:Agentic-Coding-Pipeline/tests/test_pipeline.py†L34-L44】

---

## Architecture

```mermaid
flowchart TD
  U[Developer Task] --> OR[AgenticCodingPipeline
  (Iterative Orchestrator)]
  OR -->|state| C1[GPT Coding Agent]
  OR -->|state| C2[Claude Coding Agent]
  C1 --> OR
  C2 --> OR
  OR --> F[Ruff Formatter]
  F --> OR
  OR --> T[Claude Test Author + Pytest Runner]
  T -->|tests pass?| OR
  OR --> Q[Gemini QA Reviewer]
  Q -->|PASS?| OR
  OR -->|status| OUT[Ready-to-commit Patch]
  OR -. feedback .-> C1
  OR -. feedback .-> C2
```

```text
Task
  │
  ▼
AgenticCodingPipeline (max 3 iterations)
  │  shared dict state: {task, proposed_code, tests_passed, qa_passed, feedback, ...}
  ▼
Coding agents (OpenAI + Claude)
  │  produce / refine `proposed_code`
  ▼
Formatting agents (Ruff --fix)
  │  normalize style before verification
  ▼
Testing agents (Claude writes tests → pytest run)
  │  set `tests_passed`, attach `test_output`
  ▼
QA agents (Gemini review)
  │  set `qa_passed`, attach `qa_output`
  ▼
Completion → `status="completed"` or loop with feedback until max iterations
```

---

## Operational timeline

1. **Task ingestion** – CLI seeds a shared state dict with the human request.【F:Agentic-Coding-Pipeline/pipeline.py†L21-L23】
2. **First coder pass** – GPT-based agent drafts an initial solution (or improves an existing snippet).【F:Agentic-Coding-Pipeline/agents/coding.py†L22-L36】
3. **Second coder pass** – Claude-based agent refines the proposal, incorporating earlier feedback or failures.【F:Agentic-Coding-Pipeline/run.py†L21-L28】
4. **Formatter pass** – Ruff auto-fixes lint/style deviations before any tests run.【F:Agentic-Coding-Pipeline/agents/formatting.py†L17-L26】
5. **Test synthesis** – Claude drafts pytest suites tailored to the generated code.【F:Agentic-Coding-Pipeline/agents/testing.py†L26-L38】
6. **Local execution** – Pytest runs in an isolated temp directory; stdout/stderr are captured for diagnostics.【F:Agentic-Coding-Pipeline/agents/testing.py†L34-L42】
7. **QA verdict** – Gemini reviews the candidate patch, emitting PASS/FAIL plus commentary.【F:Agentic-Coding-Pipeline/agents/qa.py†L23-L33】
8. **Loop or finish** – Failures store feedback and trigger another iteration (up to `max_iterations`).【F:Agentic-Coding-Pipeline/pipeline.py†L33-L55】

---

## Prerequisites

* **Python 3.10+** (matches the rest of the Agentic AI monorepo).
* **Local tooling** available on `$PATH`:
  * `ruff` for formatting.
  * `pytest` for executing generated suites.
* **LLM credentials** (set as environment variables):
  * `OPENAI_API_KEY` for GPT coders.
  * `ANTHROPIC_API_KEY` for Claude coders/testers.
  * `GOOGLE_API_KEY` for Gemini QA review.
* **Clean git workspace** if you want to auto-commit results with the helper in `tools/git.py`.

---

## Quickstart

```bash
# 1. Create an isolated environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install repo dependencies and tooling
pip install --upgrade pip
pip install -e .           # exposes agentic_ai.llm clients
pip install ruff pytest    # ensure local tools are present

# 3. Provide API keys (export or use a .env)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-...
export GOOGLE_API_KEY=sk-...
```

Prefer Poetry? Swap steps 1–2 with:

```bash
poetry install
poetry shell
```

---

## Configuration reference

| Knob | Where to set | Default | Effect |
| ---- | ------------ | ------- | ------ |
| `OPENAI_API_KEY` | env var | – | Authenticates the GPT-based `CodingAgent`.【F:Agentic-Coding-Pipeline/agents/coding.py†L18-L36】 |
| `ANTHROPIC_API_KEY` | env var | – | Powers the Claude-based coder and testing agent.【F:Agentic-Coding-Pipeline/run.py†L21-L28】【F:Agentic-Coding-Pipeline/agents/testing.py†L19-L40】 |
| `GOOGLE_API_KEY` | env var | – | Enables Gemini QA review verdicts.【F:Agentic-Coding-Pipeline/agents/qa.py†L16-L33】 |
| `max_iterations` | `AgenticCodingPipeline(max_iterations=...)` | `3` | Caps retries before marking the run as failed.【F:Agentic-Coding-Pipeline/pipeline.py†L19-L55】 |
| `coders`/`formatters`/`testers`/`reviewers` | Constructor args | see CLI defaults | Controls which agents participate in the loop.【F:Agentic-Coding-Pipeline/pipeline.py†L15-L18】 |

---

## Run

### CLI (batteries included)

```bash
cd Agentic-AI-Pipeline/Agentic-Coding-Pipeline
python run.py "Add pagination support to the API client"
```

The CLI wires up OpenAI + Claude coders, a Ruff formatter, Claude-powered tester, and Gemini reviewer in one command.【F:Agentic-Coding-Pipeline/run.py†L16-L33】
The script prints the final status and any captured feedback (failed tests, QA findings) for quick triage.【F:Agentic-Coding-Pipeline/run.py†L30-L33】

### Programmatic usage

```python
from agents.coding import CodingAgent
from agents.formatting import FormattingAgent
from agents.testing import TestingAgent
from agents.qa import QAAgent
from pipeline import AgenticCodingPipeline

pipeline = AgenticCodingPipeline(
    coders=[CodingAgent(name="gpt"), CodingAgent(name="claude")],
    formatters=[FormattingAgent(name="formatter")],
    testers=[TestingAgent(name="tests")],
    reviewers=[QAAgent(name="qa")],
    max_iterations=5,
)
result = pipeline.run("Implement a prime sieve")
print(result["status"], result.get("feedback"))
```

The return value is a serializable dict suitable for downstream orchestration (CI jobs, MCP routing, etc.).【F:Agentic-Coding-Pipeline/pipeline.py†L21-L55】

---

## State contract

The shared state dictionary evolves as agents run. Understanding the keys makes it easy to plug in dashboards or custom logic.

| Key | Producer | Consumer(s) | Description |
| --- | -------- | ----------- | ----------- |
| `task` | CLI / caller | All agents | Original human request seeded at pipeline start.【F:Agentic-Coding-Pipeline/pipeline.py†L21-L24】 |
| `proposed_code` | Coding agents, formatter | Testers, reviewers | Latest candidate solution being evaluated.【F:Agentic-Coding-Pipeline/agents/coding.py†L22-L36】【F:Agentic-Coding-Pipeline/agents/formatting.py†L17-L26】 |
| `tests_passed` | Testing agents | Orchestrator loop | Boolean signal to continue to QA. Failures trigger iteration feedback.【F:Agentic-Coding-Pipeline/agents/testing.py†L26-L42】【F:Agentic-Coding-Pipeline/pipeline.py†L34-L43】 |
| `test_output` | Testing agents | Humans / coders | Raw pytest stdout+stderr, preserved for diagnosis or re-prompting.【F:Agentic-Coding-Pipeline/agents/testing.py†L34-L42】 |
| `qa_passed` | QA agents | Orchestrator loop | Indicates whether QA cleared the change.【F:Agentic-Coding-Pipeline/agents/qa.py†L23-L33】【F:Agentic-Coding-Pipeline/pipeline.py†L44-L53】 |
| `qa_output` | QA agents | Humans / coders | Reviewer commentary (PASS or actionable issues).【F:Agentic-Coding-Pipeline/agents/qa.py†L23-L33】 |
| `feedback` | Orchestrator | Coders, humans | When tests/QA fail, the orchestrator surfaces the raw output as feedback for the next iteration.【F:Agentic-Coding-Pipeline/pipeline.py†L36-L50】 |
| `status` | Orchestrator | Callers | Final lifecycle marker: `completed` or `failed`.【F:Agentic-Coding-Pipeline/pipeline.py†L51-L56】 |
| `reason` | Orchestrator | Callers | Populated when a coder agent returns no code to explain the early failure.【F:Agentic-Coding-Pipeline/pipeline.py†L25-L29】 |

---

## Project structure

```
Agentic-Coding-Pipeline/
├── README.md                     # This guide
├── __init__.py                   # Package marker
├── pipeline.py                   # Iterative orchestration logic
├── run.py                        # CLI entry point
├── agents/                       # Role-specific LLM wrappers
│   ├── base.py                   # Agent protocol + base dataclass
│   ├── coding.py                 # Code synthesis agents
│   ├── formatting.py             # Ruff-backed formatter agent
│   ├── testing.py                # Test generation + execution agent
│   └── qa.py                     # LLM review agent
├── tools/                        # Optional utilities
│   ├── git.py                    # git commit helper
│   └── test_runner.py            # Standalone pytest runner helper
└── tests/
    └── test_pipeline.py          # Orchestration regression tests
```

---

## Agents (roles & prompts)

| Role | Default LLM client | Prompt strategy | Key state inputs | Key outputs |
| ---- | ------------------ | --------------- | ---------------- | ----------- |
| `CodingAgent` | `OpenAIClient` / `ClaudeClient` | Seed or improve a Python solution depending on whether `proposed_code` already exists.【F:Agentic-Coding-Pipeline/agents/coding.py†L22-L36】 | `task`, `proposed_code` | Updated `proposed_code` |
| `FormattingAgent` | Ruff CLI | Runs `ruff --fix` against a temp file and reloads the formatted contents.【F:Agentic-Coding-Pipeline/agents/formatting.py†L17-L26】 | `proposed_code` | Normalized `proposed_code` |
| `TestingAgent` | `ClaudeClient` | Generates pytest suites covering the solution, executes them, and stores stdout/stderr.【F:Agentic-Coding-Pipeline/agents/testing.py†L26-L42】 | `proposed_code` | `tests_passed`, `test_output` |
| `QAAgent` | `GeminiClient` | Requests a PASS/FAIL verdict with commentary on issues found.【F:Agentic-Coding-Pipeline/agents/qa.py†L23-L33】 | `proposed_code` | `qa_passed`, `qa_output` |

All agents share the lightweight `Agent` protocol, so custom roles (docs writers, security scanners, benchmark runners) can drop in without changing the orchestrator.【F:Agentic-Coding-Pipeline/agents/base.py†L9-L26】

---

## Prompt reference

Understanding default prompt templates helps tailor model behaviour.

* **Initial synthesis** – "Write a single Python function solving the following task. Return only code."【F:Agentic-Coding-Pipeline/agents/coding.py†L31-L34】
* **Refinement** – "Improve the following Python code to better accomplish the task" (includes task and current code).【F:Agentic-Coding-Pipeline/agents/coding.py†L25-L29】
* **Test authoring** – "Write pytest tests for the following Python code. Return only the test file contents."【F:Agentic-Coding-Pipeline/agents/testing.py†L28-L31】
* **QA review** – "Respond with PASS if the code is acceptable, otherwise describe the problems."【F:Agentic-Coding-Pipeline/agents/qa.py†L25-L31】

Swap or augment these strings in custom agents to target different languages, frameworks, or review policies.

---

## Test synthesis & execution

* **Isolation by temp directory** – Generated code and tests live in a throwaway workspace, keeping your repo pristine.【F:Agentic-Coding-Pipeline/agents/testing.py†L34-L38】
* **Pytest integration** – Subprocess execution captures stdout/stderr, storing them in `test_output` for debugging or feedback to coders.【F:Agentic-Coding-Pipeline/agents/testing.py†L34-L42】
* **Standalone helpers** – Import `tools.test_runner.run_pytest()` if you need to reuse the execution primitive in bespoke agents or CI hooks.【F:Agentic-Coding-Pipeline/tools/test_runner.py†L9-L13】
* **Regression coverage** – `tests/test_pipeline.py` mocks the LLMs to validate that the orchestrator converges on a completed state.【F:Agentic-Coding-Pipeline/tests/test_pipeline.py†L34-L44】

---

## Formatting & patch hygiene

* Ruff auto-fix keeps stylistic feedback out of the LLM loop and reduces diff churn.【F:Agentic-Coding-Pipeline/agents/formatting.py†L17-L26】
* Capture formatted snippets with git helpers for deterministic commits:

  ```python
  from tools.git import commit
  commit(["path/to/file.py"], "feat: apply automated patch")
  ```

  The helper stages provided paths and creates a commit using standard git plumbing.【F:Agentic-Coding-Pipeline/tools/git.py†L10-L14】

* Pair the helper with `status` checks to build unattended pipelines (e.g., auto-PR bots) once QA passes.

---

## Tooling & integration patterns

* **CLI orchestration** – `run.py` demonstrates how to wire agents with explicit LLM clients, making it easy to lift into Airflow, Dagster, or bespoke schedulers.【F:Agentic-Coding-Pipeline/run.py†L16-L33】
* **Custom retries** – Wrap `pipeline.run()` and inspect `feedback` to implement exponential backoff, diff-based heuristics, or fallback model selection.【F:Agentic-Coding-Pipeline/pipeline.py†L33-L55】
* **CI hooks** – Use the returned dict in a job step to decide whether to push commits, request reviews, or fail fast. The bundled unit test shows how to swap LLMs for mocks when running in headless CI.【F:Agentic-Coding-Pipeline/tests/test_pipeline.py†L16-L44】
* **Artifact capture** – Persist `proposed_code`, `test_output`, and `qa_output` to S3 or issue comments to give humans full context on automated changes.

---

## MCP integration

This pipeline registers with the shared [`mcp`](../mcp) package. The FastAPI-backed **MCPServer** exposes a unified toolbox (web search, browsing, direct LLM calls) so any pipeline in the monorepo can dispatch coding tasks remotely or as part of a larger workflow.

To plug this pipeline into the MCP network:

1. Import `AgenticCodingPipeline` in your MCP task handler.
2. Instantiate agents with the credentials available inside the MCP worker pod (often via Kubernetes secrets).
3. Invoke `pipeline.run(task)` and route the resulting state (status, feedback, artifacts) back to the caller or next graph node.
4. Optionally mount shared storage so test artifacts or generated files persist across MCP tool invocations.

---

## Extending & customization

* **Swap models** – Pass alternative `LLMClient` implementations when constructing agents (e.g., Azure OpenAI, local models).【F:Agentic-Coding-Pipeline/run.py†L21-L29】【F:Agentic-Coding-Pipeline/agents/coding.py†L16-L36】
* **Add new stages** – Extend the `formatters`, `testers`, or `reviewers` lists with additional agents (docs generation, security scans, benchmarks).【F:Agentic-Coding-Pipeline/pipeline.py†L15-L55】
* **Adjust iteration policy** – Change `max_iterations` or inject heuristics (stop early on repeated identical feedback, escalate on critical QA failures).【F:Agentic-Coding-Pipeline/pipeline.py†L19-L55】
* **Augment state** – Agents can read/write arbitrary keys; use this to track metrics, diff metadata, or artifact paths.【F:Agentic-Coding-Pipeline/agents/base.py†L9-L26】
* **Scale to multi-file edits** – Store structured payloads in `proposed_code` (e.g., dict of path → content) and customize formatter/tester agents accordingly.
* **Guardrails & policies** – Wrap coder outputs with static analyzers or allow/deny lists before tests run to catch dependency misuse or security issues.

---

## Operations & observability

* **Logging** – Instrument agents to log prompts, tokens, and runtimes before returning updated state. The orchestration loop makes a single pass per agent, making it easy to emit structured logs around each stage.【F:Agentic-Coding-Pipeline/pipeline.py†L21-L55】
* **Metrics** – Track counts of completed vs. failed runs, retry depth, and durations between state transitions. State keys (`tests_passed`, `qa_passed`) provide natural metric dimensions.【F:Agentic-Coding-Pipeline/pipeline.py†L34-L53】
* **Cost control** – Swap LLM clients or reduce `max_iterations` when cost thresholds are hit; fallback to cheaper coders or disable QA temporarily for low-risk changes.
* **Safety** – Layer in secret-scanning agents or require QA PASS + human approval before calling `tools.git.commit` in production pipelines.【F:Agentic-Coding-Pipeline/tools/git.py†L10-L14】

---

## Quality control & failure handling

* Missing coder output immediately fails the run and surfaces a diagnostic so upstream orchestrators can react.【F:Agentic-Coding-Pipeline/pipeline.py†L25-L29】
* Test and QA failures attach their raw outputs to `feedback`, giving subsequent iterations or humans concrete guidance.【F:Agentic-Coding-Pipeline/pipeline.py†L36-L50】
* Exhausting the iteration budget marks the run as `failed`, preserving the last known state for inspection.【F:Agentic-Coding-Pipeline/pipeline.py†L51-L56】
* Unit tests validate that the orchestrator reaches a completed state with deterministic mock responses, preventing regressions in the loop contract.【F:Agentic-Coding-Pipeline/tests/test_pipeline.py†L34-L44】

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| `ModuleNotFoundError: agentic_ai.llm` | Repo dependencies not installed | Run `pip install -e .` from repo root or `poetry install`. |
| `ruff: command not found` | Ruff not installed in current environment | `pip install ruff` or `poetry run ruff --version` to verify. |
| Pytest exits with import errors | Generated code expects extra dependencies | Update prompts to constrain imports or pre-install needed packages. |
| QA always fails with "PASS" missing | Reviewer prompt/casing changed | Ensure reviewer returns a string containing `PASS` on success or tweak condition accordingly.【F:Agentic-Coding-Pipeline/agents/qa.py†L25-L33】 |
| Pipeline stops after coder stage | An agent returned an empty string | Inspect `reason` for `"coder did not return code"` and adjust prompts or guardrails.【F:Agentic-Coding-Pipeline/pipeline.py†L25-L29】 |
| Iterations never succeed | Feedback not consumed by coders | Make coder prompts reference `feedback` to incorporate failures when you extend the pipeline. |

---

## FAQ

**Can I run only one coder?**  Yes. Provide a single `CodingAgent` (or even a custom agent) in the `coders` list.【F:Agentic-Coding-Pipeline/pipeline.py†L24-L33】

**How do I persist generated code to disk?**  Have an agent write `proposed_code` to the desired file path before QA, or call the git helper after completion.【F:Agentic-Coding-Pipeline/tools/git.py†L10-L14】

**Can the pipeline edit multi-file projects?**  The sample agents operate on a single code snippet, but the shared state supports richer payloads (e.g., dict of file paths). Add formatters/testers that understand your structure.【F:Agentic-Coding-Pipeline/agents/base.py†L9-L26】【F:Agentic-Coding-Pipeline/agents/testing.py†L26-L42】

**How do I integrate with CI?**  Wrap `AgenticCodingPipeline.run()` inside a job that prepares credentials and tools, then treat the returned state as the artifact for subsequent stages (commit, PR, deployment).【F:Agentic-Coding-Pipeline/pipeline.py†L21-L56】

**Where do I tweak prompts?**  Each agent defines its own prompt string—modify them directly or subclass the agent to inject dynamic templates.【F:Agentic-Coding-Pipeline/agents/coding.py†L22-L34】【F:Agentic-Coding-Pipeline/agents/testing.py†L28-L31】【F:Agentic-Coding-Pipeline/agents/qa.py†L25-L31】

---

Happy shipping! 🚀
