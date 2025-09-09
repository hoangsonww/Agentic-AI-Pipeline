# Tracing & Evaluation System

A comprehensive observability and evaluation framework that makes every agent run **traceable**, **reproducible**, and **measurable**.

## 🎯 Features

- **📊 JSONL Trace Capture**: Node-level inputs/outputs, tool I/O, timings, and state transitions
- **🔄 Reproducible Runs**: Seeded execution with mock tool responses from traces  
- **✅ Golden Task Harness**: Automated evaluation with pass/fail heuristics and scorecards
- **🔍 CLI Tools**: Chat, trace listing, replay, and comparison commands
- **🧪 Pytest Integration**: Full test suite with detailed evaluation reporting
- **🔒 Privacy-First**: Configurable data redaction and content length limits

## 🚀 Quick Start

### Enable Tracing
```bash
# Set environment variable
export ENABLE_TRACING=true

# Or use CLI flag
python -m agentic_ai.cli chat "Hello world" --trace
```

### View Traces
```bash
# List all traces
python -m agentic_ai.cli list-traces

# Show trace events
python -m agentic_ai.cli replay data/traces/chat123/run456.jsonl --show-events
```

### Run Evaluations
```bash
# Execute golden tasks
python -m evals.runner

# Run pytest evaluation suite
python -m pytest tests/test_evals.py -v
```

### Replay for Debugging
```bash
# Replay with mock tools (requires original trace)
python -m agentic_ai.cli replay data/traces/chat123/run456.jsonl --execute

# Compare original vs replay
python -m agentic_ai.cli compare-traces original.jsonl replay.jsonl
```

## 📁 Directory Structure

```
src/agentic_ai/infra/
├── trace.py          # Core tracing system with JSONL writer
└── replay.py         # Replay engine with mock tools

evals/
├── golden/           # YAML task definitions
│   ├── basic-greeting.yaml
│   ├── simple-calculation.yaml
│   └── ...
├── runner.py         # Task execution engine
└── scorer.py         # Assertion evaluation logic

data/traces/          # Trace storage
└── {chat_id}/
    └── {run_id}.jsonl

tests/test_evals.py   # Pytest integration
```

## 📊 Trace Format

Each trace is a JSONL file with timestamped events:

```json
{"event_type": "run_start", "timestamp": 1694123456.789, "node_name": "root", "chat_id": "abc123", "run_id": "def456", "data": {"start_time": "2023-09-07T10:30:56Z"}}
{"event_type": "node_start", "timestamp": 1694123456.790, "node_name": "planner", "data": {"input": {"user_message": "Hello"}}}
{"event_type": "tool_request", "timestamp": 1694123456.850, "node_name": "tools", "data": {"tool_name": "calculator", "args": {"expression": "2+2"}, "args_hash": "abc12345"}}
{"event_type": "tool_response", "timestamp": 1694123456.920, "node_name": "tools", "data": {"tool_name": "calculator", "result": "4"}, "duration_ms": 70}
{"event_type": "run_end", "timestamp": 1694123457.100, "node_name": "root", "data": {"total_duration_ms": 311}}
```

## ✅ Golden Tasks

Example task definition (`evals/golden/simple-calculation.yaml`):

```yaml
id: "simple-calculation"
description: "Test calculator tool usage"  
prompt: "What is 15 + 27 multiplied by 3?"
timeout_seconds: 60
expected_behavior: "tool_usage"
assertions:
  - type: "must_include"
    value: ["126"]
    description: "Should calculate (15 + 27) * 3 = 126"
  - type: "tool_used" 
    value: "calculator"
    description: "Should use calculator tool"
  - type: "max_tokens"
    value: 300
    description: "Keep response concise"
tags: ["math", "calculator", "tool_usage"]
```

## 🧪 Assertion Types

| Type | Description | Example |
|------|-------------|---------|
| `must_include` | Response must contain specific terms | `value: ["hello", "greeting"]` |
| `must_not_include` | Response must not contain terms | `value: ["error", "failed"]` |
| `max_tokens` | Response length limit | `value: 200` |
| `min_tokens` | Response minimum length | `value: 50` |
| `tool_used` | Specific tool must be called | `value: "calculator"` |
| `has_structure` | Response has lists/sections | `value: true` |
| `no_fabrication` | Detect made-up information | `value: true` |
| `node_sequence` | Specific workflow followed | `value: ["plan", "act", "reflect"]` |

## ⚙️ Configuration

Add to your `.env` file or environment:

```bash
# Tracing
ENABLE_TRACING=false              # Enable/disable tracing
TRACE_MAX_CONTENT_LENGTH=2000     # Max chars per field
TRACE_REDACT_PATTERNS=["api_key", "token"]  # Sensitive patterns

# Optional integrations  
ENABLE_LANGSMITH=false            # LangSmith export
LANGSMITH_API_KEY=your_key        # LangSmith API key
ENABLE_OTEL_EXPORTER=false        # OpenTelemetry export
OTEL_ENDPOINT=http://localhost:4317  # OTEL endpoint
```

## 🔒 Privacy & Security

- **Automatic Redaction**: API keys, tokens, passwords filtered from traces
- **Content Limits**: Large responses truncated to configured length
- **Local Storage**: Traces stored locally by default, not sent externally
- **Configurable Patterns**: Customize what gets redacted via `TRACE_REDACT_PATTERNS`

## 🎨 Web UI Integration

The web interface includes a "Download Trace" button after chat completion (when tracing is enabled):

```javascript
// Example: Add to your web UI
if (tracingEnabled) {
  showTraceDownloadLink(`data/traces/${chatId}/${runId}.jsonl`);
}
```

## 📈 Example Scorecard

```
==================================================
GOLDEN TASK EVALUATION SCORECARD
==================================================
Overall Pass Rate: 80.0%
Tasks Passed: 4/5
Average Score: 0.84

Task Details:
--------------------------------------------------
✅ PASS basic-greeting
  Duration: 2.1s
  Assertions: 3/3 passed
    ✓ Should include greeting or positive response
    ✓ Keep response concise  
    ✓ Should provide substantive response

✅ PASS simple-calculation  
  Duration: 3.2s
  Assertions: 3/3 passed
    ✓ Should calculate (15 + 27) * 3 = 126
    ✓ Should use calculator tool
    ✓ Keep response reasonably concise

❌ FAIL error-handling
  Duration: 1.8s
  Assertions: 2/4 passed
    ✓ Should attempt to use calculator tool
    ✗ Should explain the mathematical limitation
    ✗ Should not make up incorrect results
    ✓ Keep explanation concise
```

## 🛠️ Development

To extend the evaluation system:

1. **Add new golden tasks**: Create YAML files in `evals/golden/`
2. **Create custom assertions**: Add handlers in `evals/scorer.py`
3. **Extend tracing**: Add event types in `src/agentic_ai/infra/trace.py`  
4. **Custom replay logic**: Modify `src/agentic_ai/infra/replay.py`

## 🔄 Reproducible Runs

For deterministic testing:

```bash
# Seeded run (same seed = same behavior)
python -m agentic_ai.cli chat "Calculate 2+2" --trace --seed my_test_seed

# Compare two runs
python -m agentic_ai.cli compare-traces run1.jsonl run2.jsonl
```

## ⚡ Performance Notes

- Tracing adds ~10-20ms overhead per node transition
- Trace files are typically 1-5KB for normal conversations
- Use `TRACE_MAX_CONTENT_LENGTH` to control file size
- Disable tracing in production for best performance

---

**Ready to debug, test, and improve your agent!** 🤖✨