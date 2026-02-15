# Text-to-SQL Pipeline

A production-ready text-to-SQL pipeline with multi-provider LLM support, LangGraph orchestration, auto-execution of valid queries with human-in-the-loop approval for queries needing review, and both REST API and MCP tool interfaces.

## Features

- **Multi-provider LLM support** — Anthropic Claude, Google Gemini, and OpenAI with automatic fallback chains via LangChain
- **LangGraph ReAct agent** — SQL agent with tool-calling loop that generates SQL, executes it, and synthesizes natural language answers. Uses `interrupt()` for human review when validation errors are found
- **Multi-database support** — BigQuery, PostgreSQL, and SQLite backends
- **Dual interface** — REST API (FastAPI) and MCP tools served from the same process
- **Read-only SQL guard** — Blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, and other mutating statements at the execution layer
- **Schema-aware generation** — Automatic schema discovery with TTL-based caching, injected into LLM prompts as DDL context with few-shot examples for improved accuracy
- **Query history** — In-memory store tracking all queries with status (pending, approved, rejected, executed, failed)

## Architecture

```mermaid
graph TD
    User["User / IDE"]
    User --> REST["REST API (/api)"]
    User --> MCP["MCP Tools (/mcp)"]
    REST --> Orch["PipelineOrchestrator"]
    MCP --> Orch

    subgraph Agent["LangGraph ReAct Agent"]
        A["discover_schema<br/><i>Fetch DDL + few-shot examples</i>"]
        B["generate_query<br/><i>LLM invocation</i>"]
        C{"should_continue"}
        D["check_query<br/><i>Validate SQL</i>"]
        E{"route_after_check"}
        F["human_approval<br/><i>interrupt()</i>"]
        G{"route_after_approval"}
        H["run_query<br/><i>Execute SQL</i>"]
        END1(["END"])
        END2(["END"])

        A --> B
        B --> C
        C -- "tool call" --> D
        C -- "text answer" --> END1
        D --> E
        E -- "clean" --> H
        E -- "errors" --> F
        F --> G
        G -- "approved" --> H
        G -- "rejected" --> END2
        H -- "ReAct loop" --> B
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
│   ├── history.py        # GET /api/history
│   ├── query.py          # POST /api/query
│   └── router.py         # APIRouter aggregation
├── db/                   # Database backends
│   ├── base.py           # DatabaseBackend protocol + read-only guard
│   ├── bigquery.py       # BigQuery backend
│   ├── factory.py        # Backend factory
│   ├── postgres.py       # PostgreSQL backend
│   └── sqlite.py         # SQLite backend
├── llm/                  # LLM integration
│   ├── prompts.py        # SQL agent system prompt for ReAct loop
│   └── router.py         # Multi-provider model creation with fallbacks
├── mcp/                  # MCP tool server
│   └── tools.py          # 2 MCP tools via FastMCP
├── models/               # Pydantic models
│   ├── domain.py         # QueryRecord, TableInfo, SchemaInfo, etc.
│   ├── requests.py       # API request models
│   └── responses.py      # API response models
├── pipeline/             # LangGraph orchestration
│   ├── approval.py       # ApprovalManager state machine
│   ├── graph.py          # LangGraph ReAct agent with interrupt()
│   ├── tools.py          # run_query LangChain tool
│   └── orchestrator.py   # Thin wrapper around the graph
├── schema/               # Schema discovery
│   ├── cache.py          # TTL-based schema cache
│   └── discovery.py      # Schema discovery service
├── store/                # Query storage
│   ├── base.py           # QueryStore protocol
│   └── memory.py         # In-memory implementation
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
