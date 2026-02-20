# Text-to-SQL Pipeline

Ask questions about your data in plain English and get back SQL queries, results, and natural language answers. The pipeline connects to your database, generates SQL using an LLM, validates and executes it, and returns a human-readable response — all through a chat UI or REST API.

Supports multi-turn conversations, real-time streaming, automatic self-correction, query caching, and human-in-the-loop SQL approval. Built with FastAPI, LangChain, and LangGraph.

![Text-to-SQL Demo](assets/Text-to-SQL.gif)

## Features

- **Multi-provider LLM support** — Anthropic Claude, Google Gemini, and OpenAI with automatic fallback chains and exponential backoff retry
- **LangGraph ReAct agent** — SQL agent with tool-calling loop that generates SQL, validates results, self-corrects, and synthesizes natural language answers. Uses `interrupt()` for human review when validation errors are found
- **Multi-agent analytical queries** — Complex analytical questions are automatically classified and routed to a multi-step pipeline: plan analysis steps, execute each SQL query, synthesize comprehensive insights
- **Multi-turn conversations** — Session-based queries with LangGraph checkpoint persistence, enabling follow-up questions that reference prior context
- **SSE streaming** — Real-time Server-Sent Events streaming pipeline progress (schema discovery, SQL generation, query execution, answer generation)
- **Self-correction** — Result validation detects empty aggregates, suspicious negatives, and LIMIT mismatches, feeding warnings back to the LLM for automatic revision
- **Query caching** — In-memory cache with TTL eviction keyed on normalized question + schema hash for instant repeat answers
- **Multi-database support** — BigQuery, PostgreSQL, and SQLite backends with parameterized query timeouts
- **Persistent storage** — SQLite-backed stores for query records, sessions, and LangGraph checkpoints (configurable, defaults to in-memory)
- **Dual interface** — REST API (FastAPI) and MCP tools served from the same process
- **Read-only SQL guard** — Blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, and other mutating statements at the execution layer
- **Schema-aware generation** — Automatic schema discovery with TTL-based caching, context budgeting, and dynamic table selection (keyword or LLM-based)
- **Observability** — Structured logging, pipeline metrics, health endpoint, optional LangSmith tracing, and per-IP rate limiting

## Architecture

```mermaid
graph TD
    User["User / IDE"]
    User --> REST["REST API (/api)"]
    User --> MCP["MCP Tools (/mcp)"]
    REST --> Orch["PipelineOrchestrator"]
    MCP --> Orch

    subgraph Agent["LangGraph Pipeline"]
        A["discover_schema<br/><i>Fetch DDL + few-shot examples</i>"]
        CL{"classify_query"}

        subgraph Simple["Simple Path (ReAct Agent)"]
            B["generate_query<br/><i>LLM invocation</i>"]
            C{"should_continue"}
            D["check_query<br/><i>Validate SQL</i>"]
            E{"route_after_check"}
            F["human_approval<br/><i>interrupt()</i>"]
            G{"route_after_approval"}
            H["run_query<br/><i>Execute SQL</i>"]
            I["validate_result<br/><i>Self-correction check</i>"]
        end

        subgraph Analytical["Analytical Path (Multi-Agent)"]
            P["plan_analysis<br/><i>Create multi-step plan</i>"]
            EX["execute_plan_step<br/><i>Generate + run SQL per step</i>"]
            SY["synthesize_analysis<br/><i>Combine insights</i>"]
            VA["validate_analysis<br/><i>Quality checks</i>"]
        end

        END1(["END"])
        END2(["END"])
        END3(["END"])

        A --> CL
        CL -- "simple" --> B
        CL -- "analytical" --> P
        B --> C
        C -- "tool call" --> D
        C -- "text answer" --> END1
        D --> E
        E -- "clean" --> H
        E -- "errors" --> F
        F --> G
        G -- "approved" --> H
        G -- "rejected" --> END2
        H --> I
        I -- "ReAct loop" --> B
        P --> EX
        EX -- "more steps" --> EX
        EX -- "done" --> SY
        SY --> VA
        VA -- "needs revision" --> SY
        VA -- "passed" --> END3
    end

    Orch --> A
```

## Prerequisites

- **Python 3.13+** — [python.org/downloads](https://www.python.org/downloads/)
- **uv** (Python package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh` ([docs](https://docs.astral.sh/uv/))
- **Node.js 18+** (only for the frontend) — [nodejs.org](https://nodejs.org/)
- **An LLM API key** from at least one provider (see step 2 below). API usage is billed by the provider — expect a few cents per query.

## Quick Start

### 1. Install

```bash
git clone https://github.com/BadriPrudhvi/text-to-sql.git
cd text-to-sql
uv sync
```

### 2. Configure

Copy the example environment file and add at least one LLM API key:

```bash
cp .env.example .env
```

Edit `.env` and set your API key(s). You only need **one** provider — pick whichever you already have an account with. The fallback order is Anthropic → Google Gemini → OpenAI.

| Provider | Get your key | Env variable |
|----------|-------------|--------------|
| Anthropic (default) | [console.anthropic.com](https://console.anthropic.com/) | `ANTHROPIC_API_KEY` |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/app/apikey) | `GOOGLE_API_KEY` |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
# GOOGLE_API_KEY=             # optional
# OPENAI_API_KEY=             # optional
```

The default config uses SQLite with the included [Chinook sample database](https://github.com/lerocha/chinook-database) (`chinook.db`), which has 11 tables of music store data (artists, albums, tracks, customers, invoices, etc.). No additional database setup is needed.

### 3. Run

**Backend:**

```bash
uv run uvicorn text_to_sql.app:app --host 0.0.0.0 --port 8000
```

You should see `Uvicorn running on http://0.0.0.0:8000`. The interactive API docs are at http://localhost:8000/docs.

**Frontend (recommended way to try it):**

Open a second terminal and run:

```bash
cd frontend && npm install && npm run dev
```

Opens a chatbot UI at http://localhost:3000. The backend must be running first — the frontend proxies all API requests to port 8000.

> **Tip:** The frontend is the easiest way to explore the pipeline. Type a question, watch the pipeline steps stream in real time, and see the SQL + results. The curl commands below are useful for scripting and debugging.

### 4. Query

**Step 1 — Submit a question:**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top 5 best-selling artists?"}'
```

If the generated SQL passes validation, it executes automatically and returns results with `approval_status: "executed"`.

If the SQL has issues (e.g. references a non-existent table), the pipeline pauses and returns `approval_status: "pending"` so you can review, edit, or reject the SQL before it runs. This is the "human-in-the-loop" approval flow — proceed to Step 2.

**Step 2 — Approve (only if pending):**

```bash
curl -X POST http://localhost:8000/api/approve/{query_id} \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

You can optionally correct the SQL before approving:

```bash
curl -X POST http://localhost:8000/api/approve/{query_id} \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "modified_sql": "SELECT * FROM Artist LIMIT 10"}'
```

**Step 3 — View history:**

```bash
curl http://localhost:8000/api/history
```

### 5. Conversations (multi-turn)

For follow-up questions that reference prior context, use conversation sessions (the frontend handles this automatically):

```bash
# Create a session (requires jq: brew install jq / apt install jq)
SESSION=$(curl -s -X POST http://localhost:8000/api/conversations | jq -r .session_id)

# Ask a question
curl -X POST http://localhost:8000/api/conversations/$SESSION/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top 5 genres by track count?"}'

# Follow up (references prior context)
curl -X POST http://localhost:8000/api/conversations/$SESSION/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Now show me the revenue for those same genres"}'
```

For real-time progress updates, use the SSE streaming endpoint:

```bash
curl -N "http://localhost:8000/api/conversations/$SESSION/stream?question=How+many+albums+per+artist"
```

### Example Questions (Chinook DB)

The pipeline generates the SQL for you — just type a question. It handles JOINs, CTEs, window functions, subqueries, and more.

**Simple** (single query, instant result):
- "How many tracks are in the database?"
- "Show all albums by Led Zeppelin"
- "Top 5 genres by total sales revenue"
- "Which customers spent more than the average customer?"
- "Rank employees by their customers' total purchases"

**Analytical** (multi-step plan with synthesized insights):
- "Analyze sales trends and suggest ways to increase revenue"
- "Compare customer spending patterns across different countries"

## Configuration

All settings are configured via environment variables (or a `.env` file).

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `GOOGLE_API_KEY` | `""` | Google AI API key (for Gemini) |
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `PRIMARY_DB_TYPE` | `sqlite` | Database backend: `sqlite`, `postgres`, or `bigquery` |
| `BIGQUERY_PROJECT` | `""` | GCP project ID |
| `BIGQUERY_DATASET` | `""` | BigQuery dataset name |
| `BIGQUERY_CREDENTIALS_PATH` | `""` | Path to GCP service account JSON |
| `POSTGRES_URL` | `""` | PostgreSQL async connection string |
| `SQLITE_URL` | `sqlite+aiosqlite:///./chinook.db` | SQLite connection string |
| `DEFAULT_MODEL` | `claude-opus-4-6` | Primary LLM model (Anthropic) |
| `SECONDARY_MODEL` | `gemini-3-pro-preview` | Secondary LLM model (Google) |
| `FALLBACK_MODEL` | `gpt-4o` | Fallback LLM model (OpenAI) |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens for LLM |
| `LLM_TEMPERATURE` | `0.0` | LLM temperature |
| `SCHEMA_CACHE_TTL_SECONDS` | `3600` | Schema cache TTL in seconds |
| `SCHEMA_SELECTION_MODE` | `none` | Dynamic table selection: `none`, `keyword`, or `llm` |
| `STORAGE_TYPE` | `memory` | Store backend: `memory` or `sqlite` (persistent) |
| `STORAGE_SQLITE_PATH` | `./pipeline.db` | SQLite path for persistent storage |
| `CACHE_ENABLED` | `true` | Enable query result caching |
| `CACHE_TTL_SECONDS` | `86400` | Query cache TTL (default 24h) |
| `MAX_CORRECTION_ATTEMPTS` | `2` | Max self-correction retries per query |
| `ANALYTICAL_MAX_PLAN_STEPS` | `7` | Max analysis steps for analytical queries |
| `ANALYTICAL_MAX_SYNTHESIS_ATTEMPTS` | `1` | Max re-synthesis attempts on quality check failure |
| `DB_QUERY_TIMEOUT_SECONDS` | `30` | Database query timeout |
| `LLM_RETRY_ATTEMPTS` | `3` | LLM retry attempts on transient failure |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `20` | Per-IP rate limit on mutation endpoints |
| `LANGSMITH_API_KEY` | `""` | LangSmith API key for tracing (optional) |
| `APP_HOST` | `0.0.0.0` | Server host |
| `APP_PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Log level |

## API Endpoints

Full interactive documentation is available at http://localhost:8000/docs when the backend is running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query` | Submit a question — auto-executes if valid, returns pending if validation errors |
| `POST` | `/api/approve/{query_id}` | Approve, reject, or edit a pending query's SQL |
| `GET` | `/api/history` | Paginated query history (`limit`, `offset` params) |
| `POST` | `/api/conversations` | Create a conversation session for multi-turn queries |
| `POST` | `/api/conversations/{id}/query` | Ask a follow-up question within a session |
| `GET` | `/api/conversations/{id}/stream` | SSE stream of pipeline events (real-time progress) |
| `GET` | `/api/conversations/{id}/history` | All queries in a session |
| `GET` | `/api/cache/stats` | Cache hit/miss statistics |
| `POST` | `/api/cache/flush` | Clear the query cache |
| `GET` | `/api/health` | Health check with pipeline metrics |

## MCP Server

The backend also exposes an [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server at `/mcp`, so AI-powered editors like Claude Code, Cursor, or VS Code Copilot can query your database directly. Point your editor's MCP client to `http://localhost:8000/mcp`.

| Tool | Description |
|------|-------------|
| `generate_sql` | Generate and execute SQL from a natural language question |
| `execute_sql` | Execute a previously approved query by ID |
| `create_session` | Create a conversation session for multi-turn queries |
| `query_in_session` | Ask a follow-up question within a session |
| `get_session_history` | Get all queries in a session |

## Database Setup

### SQLite (default)

Uses the included Chinook sample database out of the box. No setup required.

```env
PRIMARY_DB_TYPE=sqlite
SQLITE_URL=sqlite+aiosqlite:///./chinook.db
```

To use your own SQLite database, change `SQLITE_URL` to point to your `.db` file.

### PostgreSQL

```env
PRIMARY_DB_TYPE=postgres
POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
```

### BigQuery

```env
PRIMARY_DB_TYPE=bigquery
BIGQUERY_PROJECT=my-gcp-project
BIGQUERY_DATASET=my_dataset
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json
```

## Testing

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run a single test
uv run pytest tests/unit/test_graph.py::test_name
```

## Project Structure

```
src/text_to_sql/
├── api/                  # REST API endpoints
│   ├── approve.py        # POST /api/approve/{id}
│   ├── cache.py          # GET /api/cache/stats, POST /api/cache/flush
│   ├── conversation.py   # Conversation session & SSE streaming endpoints
│   ├── health.py         # GET /api/health
│   ├── history.py        # GET /api/history
│   ├── query.py          # POST /api/query
│   ├── rate_limit.py     # Sliding-window per-IP rate limiter
│   └── router.py         # APIRouter aggregation
├── cache/                # Query result caching
│   └── query_cache.py    # In-memory cache with TTL + schema hash
├── db/                   # Database backends
│   ├── base.py           # DatabaseBackend protocol + read-only guard
│   ├── bigquery.py       # BigQuery backend
│   ├── factory.py        # Backend factory
│   ├── postgres.py       # PostgreSQL backend
│   └── sqlite.py         # SQLite backend
├── llm/                  # LLM integration
│   ├── prompts.py        # SQL agent system prompt for ReAct loop
│   ├── retry.py          # Tenacity-based retry with exponential backoff
│   └── router.py         # Multi-provider model creation with fallbacks
├── mcp/                  # MCP tool server
│   └── tools.py          # 5 MCP tools via FastMCP (single-shot + session-aware)
├── models/               # Pydantic models
│   ├── domain.py         # QueryRecord, SessionInfo, TableInfo, etc.
│   ├── requests.py       # API request models
│   └── responses.py      # API response models
├── observability/        # Metrics and monitoring
│   └── metrics.py        # Pipeline metrics (counters + uptime)
├── pipeline/             # LangGraph orchestration
│   ├── agents/           # Multi-agent analytical query nodes
│   │   ├── analyst.py    # Synthesis agent — combines results into insights
│   │   ├── analysis_validator.py  # Deterministic quality checks
│   │   ├── classifier.py # Query classifier (simple vs analytical)
│   │   ├── executor.py   # Plan step executor — SQL per step
│   │   ├── models.py     # Pydantic structured output models
│   │   ├── planner.py    # Analysis planner — multi-step plans
│   │   └── prompts.py    # Agent prompts
│   ├── approval.py       # ApprovalManager state machine
│   ├── graph.py          # LangGraph pipeline with classification branching
│   ├── orchestrator.py   # Session-aware orchestrator with streaming
│   ├── tools.py          # run_query LangChain tool
│   └── validators.py     # Result validation for self-correction
├── schema/               # Schema discovery
│   ├── cache.py          # TTL-based schema cache
│   ├── discovery.py      # Schema discovery service
│   └── selector.py       # Dynamic table selection (keyword/LLM)
├── store/                # Query and session storage
│   ├── base.py           # QueryStore protocol
│   ├── factory.py        # Store factory (memory vs SQLite)
│   ├── memory.py         # In-memory query store
│   ├── session.py        # SessionStore protocol + in-memory impl
│   ├── sqlite_store.py   # SQLite query store
│   └── sqlite_session_store.py  # SQLite session store
├── app.py                # FastAPI application factory
├── config.py             # Pydantic Settings configuration
└── logging.py            # structlog setup

tests/
├── conftest.py           # Shared fixtures
├── integration/          # End-to-end API tests
└── unit/                 # Unit tests for each component

frontend/                     # Next.js chatbot UI
├── src/
│   ├── app/              # Root layout and page
│   ├── components/       # Chat, pipeline, results, approval, session UI
│   ├── hooks/            # SSE streaming, chat state, session management
│   └── lib/              # API client, types, constants
├── next.config.ts        # API proxy to backend (port 8000)
└── package.json
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'text_to_sql'` | Run `uv sync` again. On macOS with Python 3.13, see the [known .pth bug workaround](https://github.com/astral-sh/uv/issues/7790). |
| `No LLM providers configured` or similar on startup | Check that `.env` exists and has at least one valid API key set. |
| Frontend shows "Failed to fetch" or blank page | Make sure the backend is running on port 8000 before starting the frontend. |
| `401 Unauthorized` from the LLM provider | Your API key is invalid or expired. Regenerate it from the provider's dashboard. |
| Queries are slow (10+ seconds) | Normal for first queries — the LLM call takes a few seconds. Subsequent identical questions hit the cache and return instantly. |

## License

MIT
