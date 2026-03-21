# Architecture — Agentic Multi-Stage Bot

> A comprehensive guide to the system design, data flows, deployment topology, and extension points of the Agentic AI monorepo.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [7-Layer Architecture](#7-layer-architecture)
- [System Topology](#system-topology)
- [Core Agent Graph (LangGraph)](#core-agent-graph-langgraph)
- [Request Lifecycle](#request-lifecycle)
- [Layer 1 — Experience](#layer-1--experience)
- [Layer 2 — Discovery](#layer-2--discovery)
- [Layer 3 — Agent Composition](#layer-3--agent-composition)
- [Layer 4 — Reasoning & Planning](#layer-4--reasoning--planning)
- [Layer 5 — Tools & API](#layer-5--tools--api)
- [Layer 6 — Memory & Feedback](#layer-6--memory--feedback)
- [Layer 7 — Infrastructure](#layer-7--infrastructure)
- [MCP Server (Control Plane)](#mcp-server-control-plane)
- [Sub-Pipelines](#sub-pipelines)
- [Social Media Automation](#social-media-automation)
- [Client SDKs](#client-sdks)
- [Data Model](#data-model)
- [Configuration](#configuration)
- [Deployment Architecture](#deployment-architecture)
- [Security Model](#security-model)
- [Extension Points](#extension-points)
- [Directory Map](#directory-map)

---

## Executive Summary

The **Agentic Multi-Stage Bot** is a production-grade, multi-stage agentic system that orchestrates LLM reasoning, autonomous tool use, and persistent memory through a **7-layer architecture**. The reference implementation is a **DossierOutreachAgent** — given a topic or company, it builds a cited briefing and optionally drafts an outreach email.

The monorepo also ships three companion pipelines (RAG, Coding, Data), a shared MCP control plane, client SDKs (Python, TypeScript, .NET 8), and enterprise deployment modules for AWS, GCP, Azure, OCI, Kubernetes, Nomad, and bare-metal.

---

## 7-Layer Architecture

Each layer has a single responsibility and communicates through well-defined interfaces.

```mermaid
graph TB
    subgraph L1["Layer 1 — Experience"]
        FASTAPI["FastAPI + SSE"]
        WEBUI["Vue.js Web UI"]
        CLI["CLI (ingest / demo)"]
    end

    subgraph L2["Layer 2 — Discovery"]
        WEBSEARCH["WebSearch\n(DuckDuckGo)"]
        WEBFETCH["WebFetch\n(httpx + trafilatura)"]
        KBSEARCH["KbSearch\n(ChromaDB)"]
    end

    subgraph L3["Layer 3 — Composition"]
        PROFILE["AgentProfile\nDossierOutreachAgent"]
        SYSTEM["System Prompt\n(SYSTEM constant)"]
    end

    subgraph L4["Layer 4 — Reasoning"]
        PLAN["Plan"]
        DECIDE["Decide"]
        ACT["Act"]
        TOOLS_NODE["ToolNode"]
        REFLECT["Reflect"]
        FINALIZE["Finalize"]
    end

    subgraph L5["Layer 5 — Tools"]
        CALC["Calculator"]
        FWRITE["FileWrite"]
        EMAIL["Emailer"]
        KB_ADD["KbAdd"]
        SM["Social Media Tools"]
    end

    subgraph L6["Layer 6 — Memory"]
        SQLITE[("SQLite\nmessages / feedback")]
        CHROMA[("ChromaDB\nvector KB")]
    end

    subgraph L7["Layer 7 — Infrastructure"]
        LOGGING["Rotating Logger"]
        RATELIMIT["Token Bucket"]
        CONFIG["Pydantic Settings"]
        DOCKER["Docker / K8s"]
    end

    L1 --> L4
    L4 --> L2
    L4 --> L5
    L4 --> L6
    L3 --> L4
    L7 -.-> L1
    L7 -.-> L4
    L7 -.-> L6
```

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **1 — Experience** | `app.py`, `cli.py`, `web/` | HTTP API, SSE streaming, static UI, CLI |
| **2 — Discovery** | `tools/webtools.py`, `tools/knowledge.py` | Web search, URL extraction, KB semantic search |
| **3 — Composition** | `layers/composition.py` | Agent profile (persona, objective, capabilities) |
| **4 — Reasoning** | `layers/reasoning.py`, `graph.py` | LangGraph state machine, lazy graph init |
| **5 — Tools** | `tools/ops.py`, `layers/tools.py` | Tool registry, Calculator, FileWrite, Emailer |
| **6 — Memory** | `memory/sql_store.py`, `memory/vector_store.py` | SQLite conversations, ChromaDB vector store |
| **7 — Infra** | `infra/logging.py`, `infra/rate_limit.py`, `config.py` | Logging, rate limiting, env config, Docker |

---

## System Topology

The full monorepo connects multiple services, pipelines, and client SDKs:

```mermaid
flowchart TB
    subgraph Clients["Client SDKs"]
        direction LR
        PY_SDK["Python"]
        TS_SDK["TypeScript"]
        NET_SDK[".NET 8"]
        BROWSER["Web UI\n(Vue.js)"]
    end

    subgraph Gateway["FastAPI Gateway — :8000"]
        direction TB
        HEALTH["/health"]
        CHAT["/api/chat\n(SSE stream)"]
        INGEST["/api/ingest*"]
        FEEDBACK["/api/feedback"]
        SOCIAL["/api/social/*"]
        CODING_API["/api/coding/*"]
        RAG_API["/api/rag/*"]
        DATA_API["/api/data/*"]
        STATIC["Static UI\n/ /coding /rag /data"]
    end

    subgraph Core["Core Agent"]
        GRAPH["LangGraph\nPlan→Decide→Act→Reflect→Finalize"]
    end

    subgraph MCP["MCP Server — :8001"]
        MCP_PIPE["/pipeline/*"]
        MCP_LLM["/llm/*"]
        MCP_SEARCH["/search /browse"]
        MCP_KB["/kb/add /kb/search"]
        MCP_FS["/fs/read /fs/write"]
    end

    subgraph Pipelines["Sub-Pipelines"]
        ACP["Agentic Coding\nGPT + Claude + Ruff\n+ Pytest + Gemini QA"]
        ARP["Agentic RAG\nGemini + FAISS\n+ Intent Router"]
        ADP["Agentic Data\nAnalysis Pipeline"]
    end

    subgraph Storage["Persistence"]
        CHROMA_DB[("ChromaDB\nVector KB")]
        SQLITE_DB[("SQLite\nConversations\n+ Feedback")]
        FILES["data/\nagent_output/\nemails/"]
    end

    subgraph LLMs["LLM Providers"]
        OPENAI["OpenAI\nGPT-4o"]
        ANTHROPIC["Anthropic\nClaude"]
        GEMINI["Google\nGemini"]
    end

    Clients --> Gateway
    CHAT --> Core
    CODING_API --> ACP
    RAG_API --> ARP
    DATA_API --> ADP
    Gateway <--> MCP
    Core --> Storage
    Core --> LLMs
    MCP --> Storage
    ACP --> MCP
    ARP --> MCP
```

---

## Core Agent Graph (LangGraph)

The heart of the system is a typed state machine implemented with LangGraph. Every step is a single atomic action — no wall-of-text dumps.

### State Definition

```python
class AgentState(TypedDict):
    messages: list          # LangChain message objects
    plan: str               # Current action plan text
    next_action: str        # Token: search|fetch|kb_search|calculate|write_file|draft_email|finalize
    citations: list[str]    # Collected citation URLs
    done: bool              # Completion flag
```

### Graph Topology

```mermaid
stateDiagram-v2
    [*] --> Plan

    Plan --> Decide

    Decide --> Act: search / fetch / kb_search\ncalculate / write_file / draft_email
    Decide --> Reflect: unknown action
    Decide --> Finalize: finalize

    Act --> ToolNode: execute tool call
    ToolNode --> Reflect: tool result

    Reflect --> Finalize: BRIEFING produced (done=true)
    Reflect --> Decide: NEXT action (done=false)

    Finalize --> [*]
```

### Node Details

| Node | Function | LLM Call | Purpose |
|------|----------|----------|---------|
| **Plan** | `planner_node()` | Yes | Creates 3-6 step action plan with KB context (RAG pre-retrieval) |
| **Decide** | `decide_node()` | Yes | Selects ONE action token from: `search`, `fetch`, `kb_search`, `calculate`, `write_file`, `draft_email`, `finalize` |
| **Act** | `act_node_builder(tools)` | Yes (with tool binding) | Binds LLM to tool schemas, forces a single structured tool call |
| **ToolNode** | LangGraph `ToolNode(tools)` | No (execution only) | Executes the tool call and returns result |
| **Reflect** | `reflect_node()` | Yes | Produces `BRIEFING: ...` (final) or `NEXT:<action>` (continue) |
| **Finalize** | `finalize_node()` | No | Sets `done=True`, terminates graph |

### Edge Routing

```mermaid
flowchart LR
    DECIDE{Decide}
    ACT[Act]
    REFLECT[Reflect]
    FINALIZE([Finalize])

    DECIDE -->|"search"| ACT
    DECIDE -->|"fetch"| ACT
    DECIDE -->|"kb_search"| ACT
    DECIDE -->|"calculate"| ACT
    DECIDE -->|"write_file"| ACT
    DECIDE -->|"draft_email"| ACT
    DECIDE -->|"finalize"| FINALIZE
    DECIDE -->|"other"| REFLECT

    ACT --> TOOLS((ToolNode))
    TOOLS --> REFLECT

    REFLECT -->|"done=true"| FINALIZE
    REFLECT -->|"done=false"| DECIDE
```

---

## Request Lifecycle

A complete chat request from the browser through the agent and back:

```mermaid
sequenceDiagram
    autonumber
    participant User as Browser / Client
    participant API as FastAPI (:8000)
    participant RL as Rate Limiter
    participant Graph as LangGraph Agent
    participant LLM as LLM Provider
    participant Tools as ToolNode
    participant KB as ChromaDB
    participant SQL as SQLite

    User->>API: POST /api/chat {chat_id, message}
    API->>RL: allow(chat_id)?
    RL-->>API: OK (token bucket)

    API->>SQL: save_turn(chat_id, "user", message)
    API->>Graph: run_chat(chat_id, message)

    Note over Graph: Plan Node
    Graph->>KB: kb_search(user_text, k=5)
    KB-->>Graph: RAG context hits
    Graph->>LLM: "Create 3-6 step plan"
    LLM-->>Graph: plan text
    Graph-->>API: SSE event: token (plan)

    Note over Graph: Decide Node
    Graph->>LLM: "Choose ONE action"
    LLM-->>Graph: "search"

    Note over Graph: Act Node
    Graph->>LLM: "Call web_search tool"
    LLM-->>Graph: tool_call(web_search, query)

    Note over Graph: ToolNode
    Graph->>Tools: execute web_search
    Tools-->>Graph: search results JSON

    Note over Graph: Reflect Node
    Graph->>LLM: "Enough info? BRIEFING or NEXT?"
    LLM-->>Graph: "NEXT: fetch"
    Graph-->>API: SSE event: token (reflection)

    Note over Graph: Loop continues...
    Graph->>LLM: (more rounds)
    LLM-->>Graph: "BRIEFING: ..."
    Graph-->>API: SSE event: token (briefing)

    Note over Graph: Finalize Node
    Graph-->>API: SSE event: done

    API->>SQL: save_turn(chat_id, "assistant", final_content)
    API-->>User: SSE stream complete
```

---

## Layer 1 — Experience

### FastAPI Application (`app.py`)

```mermaid
flowchart LR
    subgraph Routes["FastAPI Routes (46 total)"]
        direction TB
        HEALTH_R["GET /health"]
        CHAT_R["POST /api/chat (SSE)"]
        NEW["GET /api/new_chat"]
        ING["POST /api/ingest\nPOST /api/ingest_url\nPOST /api/ingest_file"]
        FB["POST /api/feedback"]
        CODING_R["POST /api/coding/run\nPOST /api/coding/stream"]
        RAG_R["GET /api/rag/new_session\nPOST /api/rag/ask"]
        DATA_R["POST /api/data/stream\nPOST /api/data/run"]
        SOCIAL_R["15x /api/social/* routes"]
        STATIC_R["GET / /app.js /styles.css\n/coding /rag /data\n/social_media.html"]
    end
```

**Key design decisions:**

- **Lifespan context manager** replaces deprecated `@app.on_event("startup")` — initializes social media services with non-fatal fallback
- **Lazy sub-pipeline imports** — Coding, RAG, Data pipelines are imported on first request via `_import_*_services()` helpers (avoids startup failures if sub-pipelines are missing)
- **Static file serving** — resolves from `web/` directory relative to project root, not `src/`
- **SSE streaming** via `sse-starlette` — each token streams immediately, `done` event signals completion

### Web UI

Zero-build SPA using Vue 3 + Marked.js via CDN. Files: `web/index.html`, `web/app.js`, `web/styles.css`.

### CLI (`cli.py`)

Two commands:
- `agentic-ai ingest <dir>` — walks directory, ingests `.txt`/`.md` files into ChromaDB
- `agentic-ai demo <prompt>` — runs a prompt through the HTTP API and streams to stdout

---

## Layer 2 — Discovery

```mermaid
flowchart LR
    QUERY["User Query"] --> WS["WebSearch\n(DuckDuckGo)"]
    QUERY --> KBS["KbSearch\n(ChromaDB)"]
    WS --> RESULTS["JSON results\n{title, url, snippet}"]
    RESULTS --> WF["WebFetch\n(httpx + trafilatura)"]
    WF --> TEXT["Clean extracted text"]
    KBS --> HITS["Ranked documents\n{id, text, metadata}"]
```

| Tool | Class | Backend | Retry |
|------|-------|---------|-------|
| `web_search` | `WebSearch(BaseTool)` | `duckduckgo-search` (DDGS) | 3x exponential backoff |
| `web_fetch` | `WebFetch(BaseTool)` | `httpx` + `trafilatura` extraction | 3x exponential backoff |
| `kb_search` | `KbSearch(BaseTool)` | ChromaDB `collection.query()` | None |
| `kb_add` | `KbAdd(BaseTool)` | ChromaDB `collection.add()` | None |

---

## Layer 3 — Agent Composition

```python
PROFILE = AgentProfile(
    name="DossierOutreachAgent",
    persona="Calm, analytical research strategist that plans first, cites sources, "
            "writes crisp briefings, and drafts professional outreach emails on request.",
    objective="Produce competitive/company/topic briefings with concrete facts and citations. "
              "When asked, draft an outreach email and save artifacts to disk.",
    capabilities=["plan", "search", "fetch", "kb_search", "summarize",
                   "calculate", "write_file", "email", "memory"]
)
```

The profile feeds into the `SYSTEM` prompt constant in `reasoning.py`, shaping all LLM interactions.

---

## Layer 4 — Reasoning & Planning

### LLM Factory

```python
def _llm():
    if settings.MODEL_PROVIDER == "anthropic":
        return ChatAnthropic(model=settings.ANTHROPIC_MODEL_CHAT, temperature=0.2)
    return ChatOpenAI(model=settings.OPENAI_MODEL_CHAT, temperature=0.2)
```

### Lazy Graph Initialization (`graph.py`)

The graph is built on first request (not at import time) to avoid API-key validation at startup:

```python
_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        _tools = registry()
        _graph = build_graph(_tools)
    return _graph
```

---

## Layer 5 — Tools & API

### Tool Registry

```python
def registry() -> List[BaseTool]:
    return [
        WebSearch(), WebFetch(), KbSearch(), KbAdd(),
        Calculator(), FileWrite(), Emailer()
    ]
```

### Tool Specifications

| Tool | Name | Input | Output | Side Effects |
|------|------|-------|--------|-------------|
| `Calculator` | `calculator` | Math expression string | Result string | None |
| `FileWrite` | `file_write` | `{path, content}` JSON | Absolute file path | Writes to `data/agent_output/` |
| `Emailer` | `emailer` | `{to, subject, body}` JSON | `.eml` file path | Writes to `data/emails/` |
| `WebSearch` | `web_search` | NL query | JSON list of results | Network call (DuckDuckGo) |
| `WebFetch` | `web_fetch` | URL string | Extracted text | Network call (target URL) |
| `KbSearch` | `kb_search` | NL query | JSON list of {id, text, metadata} | ChromaDB read |
| `KbAdd` | `kb_add` | `{id, text, metadata}` JSON | `"ok"` | ChromaDB write |

All tools extend `langchain.tools.BaseTool` with type-annotated `name: str` and `description: str` (required by Pydantic v2).

---

## Layer 6 — Memory & Feedback

### Dual Memory Architecture

```mermaid
flowchart LR
    subgraph Conversation["Conversation Memory (SQLite)"]
        direction TB
        CHATS["chats\n(id, created_at, title)"]
        MSGS["messages\n(chat_id, role, content, tool_call)"]
        FDBK["feedback\n(chat_id, message_id, rating, comment)"]
    end

    subgraph Knowledge["Knowledge Base (ChromaDB)"]
        direction TB
        COLLECTION["agentic-kb collection\n(DefaultEmbeddingFunction)"]
        DOCS["Documents\n(id, text, metadata)"]
    end

    APP["FastAPI App"] --> CONVERSATION_API["save_turn()\nhistory()\nadd_feedback()"]
    APP --> KB_API["kb_add()\nkb_search()"]
    CONVERSATION_API --> Conversation
    KB_API --> Knowledge
```

### Memory Facade (`layers/memory.py`)

```python
sql = SQLStore(sqlite_path=settings.SQLITE_PATH)
vs  = VectorStore(persist_dir=settings.CHROMA_DIR)

def save_turn(chat_id, role, content, tool_call=None): ...
def history(chat_id) -> list[dict]: ...
def add_feedback(chat_id, message_id, rating, comment): ...
def kb_add(doc_id, text, metadata=None): ...
def kb_search(query, k=5) -> list[dict]: ...
```

### SQLite Schema

```sql
CREATE TABLE chats (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    role TEXT,          -- 'user' | 'assistant'
    content TEXT,
    tool_call TEXT,     -- optional: serialized tool call
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    message_id INTEGER,
    rating INTEGER,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB Vector Store

- **Collection**: `agentic-kb`
- **Embedding**: `DefaultEmbeddingFunction()` (ONNX MiniLM-L6-v2, runs locally)
- **Persistence**: `PersistentClient(path=settings.CHROMA_DIR)`
- **Non-empty metadata enforced**: empty `{}` gets default `{"source": "api"}`

---

## Layer 7 — Infrastructure

### Logging

Rotating file handler (`5MB` max, 2 backups) + console handler. Output format:
```
2026-03-21 14:00:00 | INFO | agentic-ai | message
```

### Rate Limiting

Token-bucket algorithm per `chat_id`: 5 tokens, refills every 10 seconds. Returns `429` when exhausted.

### Configuration (`config.py`)

```python
class Settings(BaseSettings):
    MODEL_PROVIDER: Literal["openai", "anthropic"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_CHAT: str = "gpt-4o-mini"
    OPENAI_MODEL_EMBED: str = "text-embedding-3-small"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_CHAT: str = "claude-3-5-sonnet-latest"
    GOOGLE_API_KEY: str = ""
    CHROMA_DIR: str = ".chroma"
    SQLITE_PATH: str = ".sqlite/agent.db"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ".logs"
```

Loaded from `.env` via Pydantic Settings. Docker overrides via `environment:` in compose.yaml.

---

## MCP Server (Control Plane)

The MCP server unifies all pipelines and shared tooling behind a single HTTP API on port **8001**.

```mermaid
flowchart LR
    subgraph Consumers["Consumers"]
        SDK["Client SDKs"]
        CLI_C["CLI"]
        UI_C["Web UI"]
        PIPE_C["Sub-Pipelines"]
    end

    subgraph MCP_SERVER["MCP Server (:8001)"]
        direction TB
        REG["Pipeline Registry\nPOST /pipeline/{name}"]
        LLM_EP["LLM Adapters\nPOST /llm/{provider}\nPOST /llm/summarize"]
        WEB_EP["Web Tools\nGET /search /browse /research"]
        KB_EP["KB Tools\nPOST /kb/add\nGET /kb/search"]
        FS_EP["File Sandbox\nPOST /fs/write\nGET /fs/read"]
        STATUS["GET /status\nGET /pipelines"]
    end

    subgraph Adapters["Pipeline Adapters (SSE)"]
        COD_A["POST /pipeline/coding/stream"]
        RAG_A["POST /pipeline/rag/ask"]
        DAT_A["POST /pipeline/data/analyze"]
    end

    Consumers --> MCP_SERVER
    REG --> Adapters
```

### LLM Client Abstraction

Three lightweight HTTP clients (`clients.py`) — no SDK dependencies:

```mermaid
classDiagram
    class LLMClient {
        <<Protocol>>
        +complete(prompt: str) str
    }
    class OpenAIClient {
        +model: str
        +api_key: str
        +complete(prompt) str
    }
    class ClaudeClient {
        +model: str
        +api_key: str
        +complete(prompt) str
    }
    class GeminiClient {
        +model: str
        +api_key: str
        +complete(prompt) str
    }

    LLMClient <|.. OpenAIClient
    LLMClient <|.. ClaudeClient
    LLMClient <|.. GeminiClient
```

---

## Sub-Pipelines

### Agentic Coding Pipeline

```mermaid
flowchart TD
    TASK["Developer Task"] --> ORCH["AgenticCodingPipeline\n(Orchestrator)"]
    ORCH --> GPT["GPT Coding Agent"]
    ORCH --> CLAUDE["Claude Coding Agent"]
    GPT --> ORCH
    CLAUDE --> ORCH
    ORCH --> RUFF["Ruff Formatter"]
    RUFF --> ORCH
    ORCH --> TEST["Claude Test Author\n+ Pytest Runner"]
    TEST --> ORCH
    ORCH --> QA["Gemini QA Reviewer"]
    QA -->|PASS| OUT["Ready-to-commit Patch"]
    QA -->|FAIL| ORCH
```

**State keys**: `task`, `repo`, `jira`, `github`, `gpt_patch`, `claude_patch`, `chosen_patch`, `formatted_code`, `test_code`, `test_result`, `qa_verdict`, `iteration`, `status`

### Agentic RAG Pipeline

```mermaid
flowchart TD
    USER["User Query"] --> IR["Intent Router\n(Gemini Flash)"]
    IR --> PLAN["Planner\n(Gemini Pro)"]
    PLAN --> RP["Retrieval Planner"]
    RP --> VR["Vector Retriever\n(FAISS)"]
    RP --> WR["Web Retriever\n(Google CSE)"]
    VR --> WRITER["Writer\n(Gemini Pro)"]
    WR --> WRITER
    WRITER --> CRITIC["Critic\n(Gemini Pro)"]
    CRITIC -->|"follow-ups"| RP
    WRITER --> GUARD["Guardrails"]
    GUARD --> ANSWER["Answer + Evidence"]
    PLAN -.->|"session"| MEM[("File-backed\nMemory")]
```

---

## Social Media Automation

Integrated directly into the FastAPI app at `/api/social/*` with 15 endpoints:

```mermaid
flowchart LR
    subgraph API["Social Media API (/api/social/*)"]
        HEALTH_S["GET /health"]
        POST_S["POST /post"]
        GENERATE["POST /generate-content"]
        THREAD["POST /generate-thread"]
        CAMPAIGN["POST /campaigns"]
        ANALYTICS["GET /analytics"]
        TRENDING["GET /trending/{platform}"]
        SCHEDULER["POST /scheduler/start|stop"]
    end

    subgraph Platforms["Platforms"]
        TW["Twitter/X\n(Tweepy)"]
        LI["LinkedIn\n(python-linkedin-v2)"]
        IG["Instagram"]
        FB["Facebook\n(facebook-sdk)"]
    end

    subgraph Backend["Backend"]
        AGENT["SocialMediaAgent\n(LangChain AgentExecutor)"]
        SCHED["SocialMediaScheduler\n(SQLite-backed)"]
        CONTENT["ContentGenerator"]
    end

    API --> Backend
    Backend --> Platforms
```

---

## Client SDKs

```mermaid
flowchart LR
    subgraph SDKs["Client SDKs"]
        PY["Python\n(async httpx)"]
        TS["TypeScript\n(fetch + SSE)"]
        NET[".NET 8\n(HttpClient +\nIAsyncEnumerable)"]
    end

    subgraph API["Server API"]
        ENDPOINTS["/health\n/api/new_chat\n/api/chat (SSE)\n/api/ingest\n/api/feedback\n/api/rag/*"]
    end

    PY --> ENDPOINTS
    TS --> ENDPOINTS
    NET --> ENDPOINTS
```

| SDK | Location | SSE Support | Auth Pattern |
|-----|----------|-------------|-------------|
| **Python** | `clients/python/` | `async for` with httpx | Header injection |
| **TypeScript** | `clients/ts/` | EventSource / fetch | Constructor config |
| **.NET 8** | `clients/dotnet/` | `IAsyncEnumerable<SseEvent>` | `IHttpClientFactory` + DI |

---

## Data Model

### Entity Relationships

```mermaid
erDiagram
    CHAT ||--o{ MESSAGE : contains
    CHAT ||--o{ FEEDBACK : receives
    MESSAGE ||--o| FEEDBACK : "rated by"
    KB_DOCUMENT ||--o{ KB_METADATA : has

    CHAT {
        text id PK
        timestamp created_at
        text title
    }
    MESSAGE {
        int id PK
        text chat_id FK
        text role
        text content
        text tool_call
        timestamp created_at
    }
    FEEDBACK {
        int id PK
        text chat_id FK
        int message_id FK
        int rating
        text comment
        timestamp created_at
    }
    KB_DOCUMENT {
        text id PK
        text content
        vector embedding
    }
    KB_METADATA {
        text doc_id FK
        text key
        text value
    }
```

---

## Configuration

### Environment Variables

```mermaid
flowchart LR
    ENV[".env file"] --> PS["Pydantic Settings"]
    DOCKER["Docker env_file\n+ environment:"] --> PS
    CLI_ENV["CLI env vars"] --> PS
    PS --> APP["FastAPI App"]
    PS --> MCP_S["MCP Server"]
    PS --> GRAPH_S["LangGraph Agent"]
```

| Variable | Default | Used By |
|----------|---------|---------|
| `MODEL_PROVIDER` | `openai` | Reasoning layer |
| `OPENAI_API_KEY` | `""` | LLM calls |
| `ANTHROPIC_API_KEY` | `""` | LLM calls |
| `GOOGLE_API_KEY` | `""` | MCP Gemini adapter |
| `CHROMA_DIR` | `.chroma` | Vector store |
| `SQLITE_PATH` | `.sqlite/agent.db` | Conversation store |
| `APP_HOST` | `0.0.0.0` | Uvicorn bind |
| `APP_PORT` | `8000` | Uvicorn port |
| `LOG_LEVEL` | `INFO` | Logger |
| `LOG_DIR` | `.logs` | Log file directory |

---

## Deployment Architecture

### Multi-Cloud Support

```mermaid
flowchart TB
    subgraph TF["Terraform Root"]
        VAR["cloud_provider = ?"]
    end

    VAR -->|aws| AWS["AWS\nECS Fargate\nALB + CodeDeploy\nECR"]
    VAR -->|gcp| GCP["GCP\nCloud Run v2\nArtifact Registry\nCloud SQL\nCloud Armor WAF"]
    VAR -->|azure| AZ["Azure\nContainer Apps\nACR\nVNet + NSG\nLog Analytics"]
    VAR -->|oci| OCI["OCI\nContainer Instances\nOCIR\nVCN + LB"]

    subgraph K8S["Kubernetes (any cloud)"]
        STD["Standard\nDeployment"]
        BG["Blue/Green\n2 Deployments\nService switch"]
        CAN["Canary\nFlagger\nProgressive delivery"]
        SEC["Security\nNetworkPolicy\nPod Security Standards"]
    end

    subgraph ONPREM["On-Premises"]
        NOMAD_D["HashiCorp Nomad\nVault secrets\nCanary updates"]
        ANSIBLE_D["Ansible\nSystemd / Docker\nNGINX reverse proxy"]
        COMPOSE_D["Docker Compose\nApp + MCP\nVolume persistence"]
    end

    subgraph GITOPS["GitOps"]
        ARGO["ArgoCD\nSync windows\nRollout strategy"]
        FLUX["Flux v2\nImage automation\nSlack notifications"]
    end
```

### Docker Architecture

```mermaid
flowchart LR
    subgraph Build["Multi-Stage Dockerfile"]
        BUILDER["Stage 1: builder\npython:3.11-slim\nbuild-essential\npip install"]
        RUNTIME["Stage 2: runtime\npython:3.11-slim\nlibxml2 + curl\nNon-root: appuser"]
        BUILDER --> RUNTIME
    end

    subgraph Compose["Docker Compose"]
        APP_SVC["app (:8000)\n2G / 2 CPU\n/health check"]
        MCP_SVC["mcp (:8001)\n1G / 1 CPU\n/status check"]
        APP_SVC --> CHROMA_VOL[("chroma-data")]
        APP_SVC --> SQLITE_VOL[("sqlite-data")]
        MCP_SVC --> CHROMA_VOL
        MCP_SVC --> SQLITE_VOL
    end
```

### Terraform Module Matrix

| Module | Lines | Resources |
|--------|-------|-----------|
| `ecs_fargate` | 109 | ECR, ECS Cluster, Task Def, ALB, IAM |
| `ecs_blue_green` | 356 | Dual TGs, CodeDeploy, Test Listener |
| `ecs_canary` | 260 | Weighted TGs, Dual Services |
| `gcp_cloud_run` | 1,240 | Cloud Run v2, Artifact Registry, Secret Manager, Cloud SQL, VPC Connector, HTTPS LB, Cloud Armor WAF |
| `azure_container_apps` | 864 | Container Apps, ACR, VNet, NSG, Log Analytics |
| `oci_container_instances` | 1,233 | Container Instances, OCIR, VCN, NAT/IGW, LB |

---

## Security Model

```mermaid
flowchart TB
    subgraph Perimeter["Perimeter"]
        RL_SEC["Rate Limiting\n(token bucket per chat_id)"]
        CORS["CORS / Security Headers\n(via reverse proxy)"]
        TLS["TLS Termination\n(Caddy / NGINX / Cloud LB)"]
    end

    subgraph App["Application"]
        SECRETS["Pydantic Settings\n(.env never committed)"]
        SANDBOX["File Sandbox\n(data/agent_output/ only)"]
        CALC_SAFE["Calculator\n(no builtins, math only)"]
        NONROOT["Non-root Docker\n(appuser:1001)"]
    end

    subgraph Infra["Infrastructure"]
        VAULT_SEC["HashiCorp Vault\nKV + DB + PKI + Transit"]
        NETPOL["K8s NetworkPolicy\n(ingress/egress restricted)"]
        PODSEC["Pod Security Standards\n(restricted enforcement)"]
        IAM["Cloud IAM\n(least-privilege SA)"]
    end

    subgraph CI["CI/CD"]
        CODEQL["CodeQL\n(security scanning)"]
        AUDIT["pip-audit\n(dependency vulnerabilities)"]
        RUFF_SEC["Ruff\n(code quality)"]
    end

    Perimeter --> App
    App --> Infra
    CI -.-> App
```

---

## Extension Points

### Add a New Tool

1. Create `src/agentic_ai/tools/my_tool.py`:
   ```python
   class MyTool(BaseTool):
       name: str = "my_tool"
       description: str = "What it does. Input: X. Output: Y."
       def _run(self, input: str) -> str: ...
   ```
2. Register in `layers/tools.py::registry()`.
3. Add action token to `decide_node()` prompt and `act_node()` mapping.

### Add a New LLM Provider

1. Add client in `llm/clients.py` implementing `LLMClient` protocol.
2. Add provider branch in `layers/reasoning.py::_llm()`.
3. Add env vars in `config.py::Settings`.

### Add a New Sub-Pipeline

1. Create directory with `services.py` exporting a stream function.
2. Add lazy import in `app.py` following the `_import_*_services()` pattern.
3. Add SSE endpoint adapter in `mcp/server.py`.

### Change the Agent Profile

Edit `layers/composition.py::PROFILE` — persona, objective, and capabilities shape all LLM interactions via the `SYSTEM` prompt.

---

## Directory Map

```
src/agentic_ai/
├── app.py                    # FastAPI gateway (46 routes, lifespan, SSE)
├── graph.py                  # Lazy LangGraph runner
├── cli.py                    # CLI: ingest + demo
├── config.py                 # Pydantic Settings
├── layers/
│   ├── composition.py        # AgentProfile (DossierOutreachAgent)
│   ├── reasoning.py          # LangGraph state machine (6 nodes)
│   ├── memory.py             # Memory facade (SQL + Vector)
│   └── tools.py              # Tool registry (7 tools)
├── tools/
│   ├── webtools.py           # WebSearch, WebFetch
│   ├── ops.py                # Calculator, FileWrite, Emailer
│   ├── knowledge.py          # KbSearch, KbAdd
│   ├── social_media_tools.py # Social platform tools
│   └── content_generation.py # AI content generation
├── memory/
│   ├── sql_store.py          # SQLite (chats, messages, feedback)
│   └── vector_store.py       # ChromaDB (agentic-kb collection)
├── llm/
│   ├── clients.py            # OpenAI, Claude, Gemini HTTP clients
│   └── client.py             # LangChain ChatModel factory
├── infra/
│   ├── logging.py            # Rotating file + console logger
│   └── rate_limit.py         # Token-bucket rate limiter
├── agents/
│   └── social_media_agent.py # Social media AgentExecutor
├── social_media_api.py       # /api/social/* router (15 endpoints)
└── social_media_scheduler.py # Campaign scheduler (SQLite-backed)

mcp/
├── server.py                 # MCP FastAPI app (pipeline dispatch + tools)
├── schemas.py                # Pydantic request models
└── tools/
    ├── web.py                # search_ddg(), fetch_page()
    ├── kb.py                 # kb_add(), kb_search()
    └── files.py              # sandboxed read/write

clients/
├── python/                   # Async Python client SDK
├── ts/                       # TypeScript/Node client SDK
└── dotnet/                   # .NET 8 client SDK (C#)

hashicorp/terraform/
├── main.tf                   # Multi-provider root (cloud_provider var)
├── modules/
│   ├── ecs_fargate/          # AWS ECS Fargate
│   ├── ecs_blue_green/       # AWS ECS + CodeDeploy
│   ├── ecs_canary/           # AWS ECS weighted routing
│   ├── gcp_cloud_run/        # GCP Cloud Run v2
│   ├── azure_container_apps/ # Azure Container Apps
│   └── oci_container_instances/ # OCI Container Instances
├── vault/                    # Vault policy (KV, DB, PKI, Transit)
└── nomad/                    # Nomad job (dual groups, Vault integration)

k8s/
├── deployment.yaml           # Standard deployment
├── service.yaml / ingress.yaml
├── blue-green/               # Blue/green manifests
├── canary/                   # Canary + Flagger + HPA
├── network-policy.yaml       # Ingress/egress restrictions
└── pod-security.yaml         # Namespace + quotas + SA

gitops/
├── argocd/                   # Applications + Rollouts + AppProject
└── flux/                     # Sync + Image automation + Notifications
```

---

*Last updated: 2026-03-21 — v0.4.0*
