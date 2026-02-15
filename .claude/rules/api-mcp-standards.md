---
paths:
  - "src/text_to_sql/api/**"
  - "src/text_to_sql/mcp/**"
---

# API & MCP Standards

## REST API (FastAPI)

### Endpoints
- Prefix all routes with `/api`
- Use `APIRouter` per domain (query, approval, history)
- Always specify `response_model` on route decorators
- Return Pydantic models, not raw dicts

### Error Responses
- 400: Invalid request (bad status transition, validation failure)
- 404: Resource not found (unknown query_id)
- 422: Pydantic validation error (auto-handled by FastAPI)
- 500: Unhandled server error (should not happen in normal operation)

Always catch known exceptions in endpoints:
```python
try:
    ...
except KeyError:
    raise HTTPException(status_code=404, detail="...")
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### Input Validation
- All string inputs must have `max_length` via Pydantic `Field`
- `question`: max 2000 chars
- `modified_sql`: max 10000 chars
- Validate modified SQL with `check_read_only()` before accepting

### Dependency Injection
- Use FastAPI `lifespan` for app-wide singletons (DB, LLM, orchestrator)
- Access shared state via `request.app.state`
- Never create new DB connections per request

## MCP Server (FastMCP)

### Transport
- Use `fastmcp.FastMCP` (standalone package, not `mcp.server.fastmcp`)
- Mount via `mcp_server.http_app()` (Streamable HTTP transport)
- State shared via `mcp_server.state = app.state` in lifespan

### Tool Design
- Each tool has a clear docstring with `Args:` section (used by MCP clients)
- Tools return `dict` — include `query_id` for operations that need follow-up
- Tools that modify state must require prior approval (human-in-the-loop)
- Tool names use `snake_case`: `schema_discovery`, `generate_sql`, `validate_sql`, `execute_sql`

### Tool Categories
1. **Read-only**: `get_session_history` — safe to call anytime
2. **Generative**: `generate_sql`, `query_in_session` — creates records, may require approval
3. **Mutating**: `execute_sql` — only works on approved queries
4. **Session management**: `create_session` — creates new conversation sessions

## Shared Patterns
- Both API and MCP access the same `PipelineOrchestrator` and `QueryStore`
- Both enforce the same approval lifecycle: PENDING → APPROVED → EXECUTED
- Neither should bypass `check_read_only()` for any user-provided SQL
