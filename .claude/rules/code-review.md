# Code Review Standards

## Mandatory Checks (block merge if failing)

### Security
- [ ] No SQL injection: all user input validated via `check_read_only()` before execution
- [ ] No identifier injection: `validate_identifier()` called before interpolating names into SQL
- [ ] Modified SQL from users is re-validated in `approval.py`
- [ ] No secrets in code, logs, or error messages
- [ ] API inputs have max_length constraints on string fields

### Correctness
- [ ] All new async code uses `await` — no fire-and-forget coroutines
- [ ] Shared mutable state protected by `asyncio.Lock()`
- [ ] Error paths return proper HTTP status codes (404/400/500), not bare exceptions
- [ ] Database connections are properly closed in error paths

### Testing
- [ ] New code has corresponding unit tests
- [ ] Tests mock external dependencies (LLM, DB) — no real API calls
- [ ] Edge cases tested: empty input, invalid IDs, duplicate operations
- [ ] All 49+ tests pass: `uv run pytest`

## Quality Checks (should fix, won't block)
- [ ] Type hints on all functions — `mypy --strict` passes
- [ ] No unused imports or dead code
- [ ] Structured logging with `structlog`, not `print()`
- [ ] Consistent error message format across endpoints

## Review Focus Areas by File
- **db/*.py**: SQL injection, connection lifecycle, read-only enforcement
- **pipeline/graph.py**: State transitions, interrupt/resume correctness
- **api/*.py**: Input validation, error handling, response models
- **mcp/tools.py**: State access safety, tool return types
- **approval.py**: Status transition guards, SQL re-validation
