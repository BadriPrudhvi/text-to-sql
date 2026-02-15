# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A text-to-SQL pipeline that converts natural language questions into SQL queries. Valid queries auto-execute; queries with validation errors pause for human-in-the-loop review. Built with FastAPI, LangChain 1.2+, and LangGraph 1.0+ with dual interfaces (REST API + MCP tools). Requires Python 3.13+.

## Commands

```bash
# Install (requires Python 3.13+ and uv)
uv sync

# Configure (set at least one LLM API key, defaults to SQLite + Chinook sample DB)
cp .env.example .env               # then edit .env

# Run
uvicorn text_to_sql.app:app --host 0.0.0.0 --port 8000

# Test
uv run pytest                     # All tests
uv run pytest tests/unit/         # Unit tests only
uv run pytest tests/integration/  # Integration tests only
uv run pytest tests/unit/test_graph.py::test_name  # Single test

# Lint & Type Check
uv run ruff check .
uv run mypy .
```

## Architecture

### Pipeline Flow (LangGraph ReAct Agent)
```
discover_schema → generate_query → [should_continue] → check_query → [route_after_check]
                       ▲            │                                    │            │
                       │         text answer                          clean        errors
                       │            │                                    │            │
                       │           END                                  │    human_approval
                       │                                                │     │           │
                       └──────────────────── run_query ◄────────────────┘  approved   rejected
                                                                                        │
                                                                                       END
```
Uses `SQLAgentState(MessagesState)` — a hybrid of LangGraph's MessagesState with custom fields (`generated_sql`, `validation_errors`, `result`, `answer`, `error`). The LLM is bound with a `run_query` tool. After `run_query`, the loop returns to `generate_query` where the model sees results in message history and generates a natural language answer (no tool calls → routes to END). Queries with validation errors route to `human_approval` which uses LangGraph's `interrupt()` to pause for human review. Resume with `Command(resume={"approved": True, "modified_sql": "..."})`. Read-only enforcement is handled by the database backends (`check_read_only()` in `db/*.py`) as defense-in-depth.

### Source Layout (`src/text_to_sql/`)
- **api/**: FastAPI REST endpoints — `POST /api/query`, `POST /api/approve/{id}`, `GET /api/history`
- **pipeline/**: LangGraph orchestration — `graph.py` (StateGraph with 5 nodes, ReAct loop), `tools.py` (run_query LangChain tool), `orchestrator.py` (coordinator), `approval.py` (HITL manager with SQL re-validation)
- **llm/**: LangChain provider integration via `init_chat_model()` — fallback chain: Anthropic → Google → OpenAI. `prompts.py` has the SQL agent system prompt with schema-agnostic few-shot examples.
- **db/**: Database backends via protocol pattern — BigQuery, PostgreSQL, SQLite. All async via SQLAlchemy
- **mcp/**: FastMCP tool server at `/mcp` (Streamable HTTP via `http_app()`) — 2 tools: generate_sql, execute_sql
- **schema/**: Schema discovery with TTL-based in-memory caching, formats as DDL for LLM context
- **store/**: Query record storage via protocol — in-memory with asyncio.Lock
- **models/**: Pydantic v2 domain models, request/response schemas with input constraints
- **config.py**: Pydantic Settings, all config via env vars
- **app.py**: FastAPI factory with lifespan-based dependency injection
- **logging.py**: structlog with rich ConsoleRenderer (TTY) / JSONRenderer (production)

### Security Model
- **Read-only SQL guard** (`db/base.py`): strips comments, blocks multi-statement, scans all tokens for forbidden DML/DDL keywords, only allows SELECT/WITH
- **Identifier validation** (`db/base.py`): validates table/column names before SQL interpolation
- **Modified SQL re-validation** (`approval.py`): user-modified SQL runs through `check_read_only()` before acceptance
- **Input constraints**: `max_length` on all user-provided strings (question: 2000, modified_sql: 10000)
- **API error boundaries**: `KeyError` → 404, `ValueError` → 400, structured error responses

### Key Patterns
- **Protocol-based abstractions**: `DatabaseBackend` and `QueryStore` are protocols — extend by implementing the protocol
- **Factory pattern**: `db/factory.py` creates backends from config
- **Async throughout**: All I/O (DB, LLM, cache) is async, shared state protected by `asyncio.Lock`
- **Strict typing**: mypy strict mode, Pydantic v2 models everywhere

### Test Setup
- `conftest.py` auto-sets SQLite env, provides `mock_chat_model` (FakeToolChatModel with tool call + answer responses), creates test app with lifespan
- All LLM calls are mocked in tests — never hits real providers
- Integration tests seed an in-memory SQLite with a sample `users` table

### Configuration (env vars / `.env`)
- At least one LLM key required: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or `OPENAI_API_KEY`
- Database: `PRIMARY_DB_TYPE` + provider-specific vars (`POSTGRES_URL`, `SQLITE_URL`, `BIGQUERY_*`)
- Models: `DEFAULT_MODEL`, `SECONDARY_MODEL`, `FALLBACK_MODEL`

## Rules

Detailed coding standards and review checklists are in `.claude/rules/`:
- `coding-python.md` — Python/async/Pydantic/testing conventions
- `git-workflow.md` — branch strategy, commit messages, pre-commit checks
- `code-review.md` — mandatory security, correctness, and testing checklists
- `api-mcp-standards.md` — REST API and MCP tool design patterns
