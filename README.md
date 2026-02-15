# Text-to-SQL Pipeline

An enterprise-grade text-to-SQL pipeline with multi-turn conversations, SSE streaming, self-correction, query caching, and human-in-the-loop approval. Built with FastAPI, LangChain, and LangGraph.

## Features

- **Multi-provider LLM support** — Anthropic Claude, Google Gemini, and OpenAI with automatic fallback chains and exponential backoff retry
- **LangGraph ReAct agent** — SQL agent with tool-calling loop that generates SQL, validates results, self-corrects, and synthesizes natural language answers. Uses `interrupt()` for human review when validation errors are found
- **Multi-agent analytical queries** — Complex analytical questions are automatically classified and routed to a multi-step pipeline: plan analysis steps, execute each SQL query, synthesize comprehensive insights with actionable recommendations
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

## Quick Start

### 1. Install

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### 2. Configure

Copy the example environment file and add at least one LLM API key:

```bash
cp .env.example .env
```

Edit `.env` and set your API key(s). Only providers with keys will be used — the fallback order is Anthropic → Google Gemini → OpenAI.

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
# GOOGLE_API_KEY=             # optional
# OPENAI_API_KEY=             # optional
```

The default config uses SQLite with the included [Chinook sample database](https://github.com/lerocha/chinook-database) (`chinook.db`), which has 11 tables of music store data (artists, albums, tracks, customers, invoices, etc.). No additional database setup is needed.

### 3. Run

```bash
uvicorn text_to_sql.app:app --host 0.0.0.0 --port 8000
```

The API docs are available at http://localhost:8000/docs.

### 4. Query

**Step 1 — Submit a question:**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top 5 best-selling artists?"}'
```

If the generated SQL is valid, it auto-executes and returns results immediately with `approval_status: "executed"`.

If the SQL has validation errors, the response will have `approval_status: "pending"` — proceed to Step 2 to review and approve.

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

For follow-up questions that reference prior context, use conversation sessions:

```bash
# Create a session
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

The pipeline handles queries from simple lookups to complex analytics:

| Difficulty | Question | SQL Pattern |
|-----------|----------|-------------|
| Basic | "How many tracks are in the database?" | `SELECT COUNT(*) FROM Track` |
| Filter | "List all tracks longer than 5 minutes" | `SELECT Name FROM Track WHERE Milliseconds > 300000` |
| JOIN | "Show all albums by Led Zeppelin" | `SELECT al.Title FROM Artist ar JOIN Album al ON ar.ArtistId = al.ArtistId WHERE ar.Name = 'Led Zeppelin'` |
| Aggregate | "Top 5 genres by number of tracks" | `SELECT g.Name, COUNT(*) FROM Genre g JOIN Track t ON g.GenreId = t.GenreId GROUP BY g.GenreId ORDER BY COUNT(*) DESC LIMIT 5` |
| Multi-JOIN | "Top 5 genres by total sales revenue" | `SELECT g.Name, SUM(il.UnitPrice * il.Quantity) FROM Genre g JOIN Track t ON g.GenreId = t.GenreId JOIN InvoiceLine il ON t.TrackId = il.TrackId GROUP BY g.GenreId ORDER BY 2 DESC LIMIT 5` |
| Subquery | "Customers who spent more than average" | `SELECT c.FirstName, c.LastName, SUM(i.Total) FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId HAVING SUM(i.Total) > (SELECT AVG(t) FROM (SELECT SUM(Total) t FROM Invoice GROUP BY CustomerId))` |
| Window | "Rank employees by their customers' total purchases" | `SELECT e.FirstName, e.LastName, SUM(i.Total), RANK() OVER (ORDER BY SUM(i.Total) DESC) FROM Employee e JOIN Customer c ON e.EmployeeId = c.SupportRepId JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY e.EmployeeId` |
| Analytical | "Analyze sales data and recommend ways to increase revenue" | Multi-step plan: monthly trends, top genres, customer segments → synthesized insights with recommendations |

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

## LLM Provider Setup

The pipeline uses LangChain's native provider integrations with `.with_fallbacks()` for automatic failover.

**Anthropic (default):** Set `ANTHROPIC_API_KEY`. Uses `ChatAnthropic` with Claude Opus 4.6.

**Google Gemini:** Set `GOOGLE_API_KEY`. Uses `ChatGoogleGenerativeAI` with Gemini 3 Pro.

**OpenAI:** Set `OPENAI_API_KEY`. Uses `ChatOpenAI` with GPT-4o.

Configure any combination. The fallback chain is built from all providers with valid keys, in the order listed above.

## API Reference

### `POST /api/query`

Submit a natural language question. Valid queries auto-execute and return results immediately. Queries with validation errors pause for human review.

**Request:**
```json
{
  "question": "How many users signed up last month?"
}
```

**Response (auto-executed):**
```json
{
  "query_id": "abc-123",
  "question": "How many users signed up last month?",
  "generated_sql": "SELECT count(*) FROM users WHERE created_at >= '2026-01-01'",
  "validation_errors": [],
  "approval_status": "executed",
  "message": "Query executed successfully.",
  "result": [{"count": 42}],
  "answer": "There were 42 users who signed up last month.",
  "error": null
}
```

**Response (pending approval):**
```json
{
  "query_id": "abc-456",
  "question": "How many items in stock?",
  "generated_sql": "SELECT count(*) FROM nonexistent_table",
  "validation_errors": ["no such table: nonexistent_table"],
  "approval_status": "pending",
  "message": "SQL generated. Awaiting approval.",
  "result": null,
  "answer": null,
  "error": null
}
```

### `POST /api/approve/{query_id}`

Approve or reject a pending query. Approved queries are executed immediately.

**Request:**
```json
{
  "approved": true,
  "modified_sql": null
}
```

**Response:**
```json
{
  "query_id": "abc-123",
  "approval_status": "executed",
  "result": [{"count": 42}],
  "answer": "There are 42 items.",
  "error": null
}
```

You can optionally edit the SQL before approving by passing `modified_sql`.

### `GET /api/history`

Get paginated query history.

**Query params:** `limit` (default 50), `offset` (default 0)

**Response:**
```json
{
  "queries": [...],
  "total": 12
}
```

### `POST /api/conversations`

Create a new conversation session for multi-turn queries.

**Response:**
```json
{
  "session_id": "uuid-here"
}
```

### `POST /api/conversations/{session_id}/query`

Submit a question within a conversation session. Follow-up questions can reference prior context.

**Request:**
```json
{
  "question": "Now break that down by region"
}
```

### `GET /api/conversations/{session_id}/stream`

Stream pipeline events via SSE. Pass the question as a query parameter.

**Query params:** `question` (required)

**Events (simple path):** `schema_discovery_started`, `schema_discovered`, `classifying_query`, `query_classified`, `llm_generation_started`, `sql_generated`, `validation_passed`, `query_execution_started`, `query_executed`, `answer_generated`, `done`

**Events (analytical path):** `schema_discovery_started`, `schema_discovered`, `classifying_query`, `query_classified`, `planning_analysis`, `analysis_plan_created`, `plan_step_started`, `plan_step_sql_generated`, `plan_step_executed`, `plan_step_failed`, `analysis_synthesis_started`, `analysis_complete`, `analysis_validation_passed`, `done`

### `GET /api/conversations/{session_id}/history`

Get all queries in a conversation session.

### `GET /api/cache/stats`

Get cache hit/miss statistics.

### `POST /api/cache/flush`

Flush all cached queries.

### `GET /api/health`

Health check with pipeline metrics (queries total, executed, failed, cache hits/misses, retries, corrections).

## MCP Tools

Two MCP tools are available at `/mcp` via Streamable HTTP transport:

| Tool | Description |
|------|-------------|
| `generate_sql` | Generate SQL from a natural language question. Valid queries auto-execute and return results. Queries with validation errors return pending status for approval. |
| `execute_sql` | Execute a previously approved SQL query by `query_id`. |

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
│   └── tools.py          # 2 MCP tools via FastMCP
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
```

## License

MIT
