---
paths:
  - "src/**"
  - "tests/**"
---

# Python Coding Standards

## Language & Typing
- Python 3.13+ required — use modern union syntax (`str | None`), not `Optional`
- `from __future__ import annotations` in every file for forward references
- All functions must have type hints — enforced via `mypy --strict`
- Use `Protocol` for interfaces, not ABCs

## Pydantic v2
- Always use `ConfigDict` (not inner `class Config`)
- Use `Field(...)` for required fields with constraints
- Use `model_dump(mode="json")` for serialization, never `.dict()`
- Use `model_copy(update={...})` for immutable updates
- Use `field_validator` with `@classmethod` decorator, not deprecated `@validator`

## Async
- All I/O operations must be `async`/`await`
- Use `asyncio.Lock()` for shared mutable state in async contexts
- Use SQLAlchemy `async with engine.connect()` — never sync connections
- Use `asyncio.get_running_loop().run_in_executor()` for blocking I/O (e.g., BigQuery SDK)

## Error Handling
- API endpoints: catch `KeyError` → 404, `ValueError` → 400, let others bubble to 500
- Never catch bare `Exception` unless re-raising or logging + returning structured error
- Database backends: return error lists from `validate_sql`, raise from `execute_sql`

## Security
- Always run `check_read_only()` before executing user-provided SQL
- Always call `validate_identifier()` before interpolating table/column names into SQL
- Never use f-strings for SQL without prior validation
- Never trust modified SQL from users — re-validate before execution

## Package Management
- Use **uv** (not pip): `uv sync`, `uv run pytest`, `uv run uvicorn`
- Lock file: `uv lock` to regenerate `uv.lock`

## Testing
- Use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock LLMs with `FakeListChatModel` — never call real providers in tests
- Use `monkeypatch.setenv` for env vars, never hardcode secrets
- Integration tests use in-memory SQLite (`sqlite+aiosqlite://`)

## Logging
- Use `structlog.get_logger()` — never `print()` or `logging.getLogger()`
- Log structured data: `logger.info("event_name", key=value)`
