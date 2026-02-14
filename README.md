# Text-to-SQL Pipeline

A production-ready text-to-SQL pipeline with multi-provider LLM support, LangGraph orchestration, human-in-the-loop approval, and both REST API and MCP tool interfaces.

## Features

- **Multi-provider LLM support** — Anthropic Claude, Google Gemini, and OpenAI with automatic fallback chains via LangChain
- **LangGraph pipeline** — StateGraph orchestration with `interrupt()` for human-in-the-loop approval before any SQL execution
- **Multi-database support** — BigQuery, PostgreSQL, and SQLite backends
- **Dual interface** — REST API (FastAPI) and MCP tools served from the same process
- **Read-only SQL guard** — Blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, and other mutating statements at the execution layer
- **Schema-aware generation** — Automatic schema discovery with TTL-based caching, injected into LLM prompts as DDL context
- **Query history** — In-memory store tracking all queries with status (pending, approved, rejected, executed, failed)

## Architecture

```
                         ┌───────────────┐
                         │   User / IDE  │
                         └──────┬────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │                             │
           REST API (/api)               MCP Tools (/mcp)
                  │                             │
                  └─────────────┬───────────────┘
                                │
                     PipelineOrchestrator
                                │
                    ┌───────────▼───────────┐
                    │   LangGraph Pipeline  │
                    │                       │
                    │  discover_schema      │
                    │       ↓               │
                    │  generate_sql         │
                    │       ↓               │
                    │  validate_sql         │
                    │       ↓               │
                    │  human_approval       │ ← interrupt() pauses here
                    │       ↓               │
                    │  execute_sql          │ ← runs only if approved
                    └───────────────────────┘
```

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

Copy the example environment file and set your API keys:

```bash
cp .env.example .env
```

You need at least one LLM provider key. The fallback order is: Anthropic → Google Gemini → OpenAI.

```env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...          # optional
OPENAI_API_KEY=sk-...       # optional
```

### 3. Run

```bash
uvicorn text_to_sql.app:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker compose up
```

## Configuration

All settings are configured via environment variables (or a `.env` file).

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `GOOGLE_API_KEY` | `""` | Google AI API key (for Gemini) |
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `PRIMARY_DB_TYPE` | `bigquery` | Database backend: `bigquery`, `postgres`, or `sqlite` |
| `BIGQUERY_PROJECT` | `""` | GCP project ID |
| `BIGQUERY_DATASET` | `""` | BigQuery dataset name |
| `BIGQUERY_CREDENTIALS_PATH` | `""` | Path to GCP service account JSON |
| `POSTGRES_URL` | `""` | PostgreSQL async connection string |
| `SQLITE_URL` | `sqlite+aiosqlite:///./local.db` | SQLite connection string |
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

Submit a natural language question. Returns generated SQL pending approval.

**Request:**
```json
{
  "question": "How many users signed up last month?"
}
```

**Response:**
```json
{
  "query_id": "abc-123",
  "question": "How many users signed up last month?",
  "generated_sql": "SELECT count(*) FROM users WHERE created_at >= '2026-01-01'",
  "validation_errors": [],
  "approval_status": "pending",
  "message": "SQL generated. Awaiting approval."
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

Four MCP tools are available at `/mcp` via SSE transport:

| Tool | Description |
|------|-------------|
| `schema_discovery` | Discover database schema (tables, columns, types). Supports `force_refresh`. |
| `generate_sql` | Generate SQL from a natural language question. Returns pending SQL for approval. |
| `validate_sql` | Validate a SQL query against the database without executing it. |
| `execute_sql` | Execute a previously approved SQL query by `query_id`. |

## Database Setup

### BigQuery

```env
PRIMARY_DB_TYPE=bigquery
BIGQUERY_PROJECT=my-gcp-project
BIGQUERY_DATASET=my_dataset
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json
```

### PostgreSQL

```env
PRIMARY_DB_TYPE=postgres
POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
```

### SQLite

```env
PRIMARY_DB_TYPE=sqlite
SQLITE_URL=sqlite+aiosqlite:///./local.db
```

## Testing

```bash
# Run all tests
pytest

# With coverage
coverage run -m pytest && coverage report

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
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
│   ├── prompts.py        # LangChain ChatPromptTemplate for SQL generation
│   ├── router.py         # Multi-provider model creation with fallbacks
│   └── sql_generator.py  # SQL generation chain (prompt | model)
├── mcp/                  # MCP tool server
│   └── tools.py          # 4 MCP tools via FastMCP
├── models/               # Pydantic models
│   ├── domain.py         # QueryRecord, TableInfo, SchemaInfo, etc.
│   ├── requests.py       # API request models
│   └── responses.py      # API response models
├── pipeline/             # LangGraph orchestration
│   ├── approval.py       # ApprovalManager state machine
│   ├── graph.py          # LangGraph StateGraph with interrupt()
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
