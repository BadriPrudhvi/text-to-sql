# Git Workflow

## Branch Strategy
- `main` — stable, production-ready code
- Feature branches: `feat/<description>` (e.g., `feat/add-postgres-backend`)
- Bug fixes: `fix/<description>` (e.g., `fix/sql-injection-guard`)
- Chores: `chore/<description>` (e.g., `chore/update-deps`)

## Commit Messages
Use conventional commits:
```
<type>(<scope>): <description>

[optional body]
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `security`

Scopes: `api`, `pipeline`, `llm`, `db`, `mcp`, `schema`, `config`, `deps`

Examples:
- `feat(api): add pagination to history endpoint`
- `fix(db): harden SQL read-only guard against comment injection`
- `security(approval): re-validate modified SQL before execution`

## Pre-Commit Checks
Before committing, always run:
```bash
uv run pytest                 # All tests pass
uv run ruff check .           # No lint errors
```

## Pull Request Rules
- PR title follows conventional commit format
- All tests must pass
- No security regressions (SQL injection, unvalidated input, etc.)
- One logical change per PR — don't mix features with refactors

## What NOT to Commit
- `.env` files or API keys
- `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`
- `uv.lock` changes unrelated to your dependency changes
- Large generated files or binary artifacts
