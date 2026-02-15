# CLAUDE.md

## Project Overview

Text-to-SQL pipeline: natural language → SQL → results. Valid queries auto-execute; queries with validation errors pause for human review. Built with FastAPI, LangChain, LangGraph. Python 3.13+.

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

LangGraph ReAct agent with 5 nodes: `discover_schema → generate_query → check_query → run_query → generate_query` (loop). State: `SQLAgentState(MessagesState)` with fields `generated_sql`, `validation_errors`, `result`, `answer`, `error`. LLM is bound with `run_query` tool. After execution, loop returns to `generate_query` — text answer (no tool calls) routes to END. Validation errors route to `human_approval` using `interrupt()`. Resume with `Command(resume={"approved": True, "modified_sql": "..."})`.

### Schema Management

- **Metadata**: All backends (Postgres, BigQuery, SQLite) populate `TableInfo.description` and `ColumnInfo.description` from DB catalogs. SQLite uses optional JSON metadata file (`SQLITE_METADATA_PATH`).
- **Filtering**: `schema_include_tables` / `schema_exclude_tables` config. Include takes precedence.
- **Context budgeting**: `context_max_tokens` × `context_schema_budget_pct` limits schema DDL in prompt. Tables with descriptions prioritized. Omitted tables listed in comment. Message history truncated to `context_history_max_messages`.
- **Dynamic selection**: `schema_selection_mode` (`none`/`keyword`/`llm`). Keyword mode scores tables by token overlap with question. LLM mode asks model to pick relevant tables (falls back to keyword on failure).

### Source Layout (`src/text_to_sql/`)

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI endpoints — `POST /api/query`, `POST /api/approve/{id}`, `GET /api/history` |
| `pipeline/` | LangGraph graph (`graph.py`), `run_query` tool (`tools.py`), orchestrator, approval manager |
| `llm/` | LLM provider fallback chain (Anthropic → Google → OpenAI), system prompt with few-shot examples, token estimation (`tokens.py`) |
| `db/` | Database backends (BigQuery, PostgreSQL, SQLite) via `DatabaseBackend` protocol |
| `mcp/` | FastMCP server at `/mcp` — 2 tools: `generate_sql`, `execute_sql` |
| `schema/` | Schema discovery with TTL-based caching, table filtering (include/exclude), budgeted rendering, dynamic table selection (`selector.py`) |
| `store/` | Query record storage via `QueryStore` protocol |
| `models/` | Pydantic v2 domain models and request/response schemas |

### Security (enforce during code review)

- **Read-only SQL guard** (`db/base.py`): blocks DML/DDL, only allows SELECT/WITH
- **Identifier validation** (`db/base.py`): validates table/column names before interpolation
- **Modified SQL re-validation** (`approval.py`): user-edited SQL re-checked before execution
- **Input constraints**: `max_length` on all user strings (question: 2000, modified_sql: 10000)

### Test Setup

- `conftest.py`: auto-sets SQLite env, provides `FakeToolChatModel` (tool call + answer pairs), creates test app
- All LLM calls mocked — never hits real providers
- Integration tests use in-memory SQLite with sample `users` table

## Rules

Coding standards and review checklists in `.claude/rules/`:
- `coding-python.md` — Python/async/Pydantic/testing conventions
- `git-workflow.md` — branch strategy, commit messages, pre-commit checks
- `code-review.md` — mandatory security, correctness, and testing checklists
- `api-mcp-standards.md` — REST API and MCP tool design patterns
