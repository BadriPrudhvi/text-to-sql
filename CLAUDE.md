# CLAUDE.md

## Project Overview

Text-to-SQL pipeline: natural language → SQL → results. Multi-turn conversations, SSE streaming, self-correction, query caching, human-in-the-loop approval. Built with FastAPI, LangChain, LangGraph. Python 3.13+.

## Commands

```bash
uv sync                                          # Install
cp .env.example .env                             # Configure (set at least one LLM API key)
uvicorn text_to_sql.app:app --host 0.0.0.0 --port 8000  # Run
uv run pytest                                    # Test (all)
uv run pytest tests/unit/test_graph.py::test_name # Test (single)
uv run ruff check .                              # Lint
uv run mypy .                                    # Type check
```

## Architecture

### Pipeline Flow

LangGraph pipeline with **query classification** branching into simple or analytical paths. State: `SQLAgentState(MessagesState)` with fields `generated_sql`, `validation_errors`, `result`, `answer`, `error`, `correction_attempts`, `query_type`, `analysis_plan`, `plan_results`, `current_step`, `synthesis_attempts`.

**Simple path** (6 nodes): `discover_schema → classify_query → generate_query → check_query → run_query → validate_result → generate_query` (ReAct loop). Text answer routes to END. Validation errors route to `human_approval` using `interrupt()`. Resume with `Command(resume={"approved": True, "modified_sql": "..."})`.

**Analytical path** (5 new agent nodes): `discover_schema → classify_query → plan_analysis → execute_plan_step (loop) → synthesize_analysis → validate_analysis → END`. The classifier uses LLM structured output to route queries. The planner creates multi-step analysis plans (max `analytical_max_plan_steps`). The executor generates SQL per step, validates, and executes (failures recorded but don't block). The analyst synthesizes all results into actionable insights. The validator runs deterministic quality checks and optionally triggers re-synthesis.

All nodes emit SSE events via `get_stream_writer()`. Self-correction up to `max_correction_attempts` on simple path.

### Multi-Turn & Streaming

Sessions (`POST /api/conversations`) share LangGraph checkpoint state via session_id = thread_id, enabling follow-up questions. SSE streaming via `sse-starlette` emits granular events per node. Storage: `STORAGE_TYPE=memory` (default) or `sqlite` (persistent queries, sessions, and LangGraph checkpoints via `AsyncSqliteSaver`).

### Schema Management

- **Metadata**: All backends populate `TableInfo.description` and `ColumnInfo.description` from DB catalogs. SQLite uses optional JSON metadata file (`SQLITE_METADATA_PATH`).
- **Filtering**: `schema_include_tables` / `schema_exclude_tables` config. Include takes precedence.
- **Context budgeting**: `context_max_tokens` × `context_schema_budget_pct` limits schema DDL in prompt. Tables with descriptions prioritized. Message history truncated to `context_history_max_messages`.
- **Dynamic selection**: `schema_selection_mode` (`none`/`keyword`/`llm`). Keyword mode scores tables by token overlap. LLM mode asks model to pick relevant tables (falls back to keyword on failure).

### Reliability

- **LLM retry**: Tenacity exponential backoff for transient failures (`llm/retry.py`)
- **DB query timeouts**: Parameterized timeouts across all backends
- **Rate limiting**: Sliding-window per-IP on mutation endpoints (`api/rate_limit.py`)
- **Query cache**: In-memory, keyed on normalized question + schema hash, TTL-based eviction
- **Metrics**: Counters for queries, cache hits/misses, retries, corrections (`GET /api/health`)

### Source Layout (`src/text_to_sql/`)

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI endpoints — query, approve, history, conversations, cache, health |
| `pipeline/` | LangGraph graph, orchestrator, approval manager, result validators |
| `pipeline/agents/` | Multi-agent nodes: classifier, planner, executor, analyst, analysis validator |
| `llm/` | LLM provider fallback chain (Anthropic → Google → OpenAI), prompts, retry logic |
| `db/` | Database backends (BigQuery, PostgreSQL, SQLite) via `DatabaseBackend` protocol |
| `mcp/` | FastMCP server at `/mcp` — 2 tools: `generate_sql`, `execute_sql` |
| `schema/` | Schema discovery, TTL caching, filtering, budgeted rendering, dynamic selection |
| `store/` | Query and session storage — in-memory and SQLite implementations |
| `cache/` | Query result cache with TTL and schema-hash invalidation |
| `observability/` | Pipeline metrics collection |
| `models/` | Pydantic v2 domain models and request/response schemas |

### Security (enforce during code review)

- **Read-only SQL guard** (`db/base.py`): blocks DML/DDL, only allows SELECT/WITH
- **Identifier validation** (`db/base.py`): validates table/column names before interpolation
- **Modified SQL re-validation** (`approval.py`): user-edited SQL re-checked before execution
- **Input constraints**: `max_length` on all user strings (question: 2000, modified_sql: 10000)
- **Rate limiting**: Sliding-window per-IP on all mutation endpoints
- **Parameterized timeouts**: DB query timeouts use parameterized queries (not string interpolation)

### Test Setup

- `conftest.py`: auto-sets SQLite env + memory storage, provides `FakeToolChatModel` (tool call + answer pairs), creates test app
- All LLM calls mocked — never hits real providers
- Integration tests use in-memory SQLite with sample `users` table

## Rules

Coding standards and review checklists in `.claude/rules/`:
- `coding-python.md` — Python/async/Pydantic/testing conventions
- `git-workflow.md` — branch strategy, commit messages, pre-commit checks
- `code-review.md` — mandatory security, correctness, and testing checklists
- `api-mcp-standards.md` — REST API and MCP tool design patterns
