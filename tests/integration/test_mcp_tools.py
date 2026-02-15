from __future__ import annotations

from types import SimpleNamespace

import pytest
from asgi_lifespan import LifespanManager
from fastmcp import Client
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from tests.conftest import FakeToolChatModel, make_agent_responses
from text_to_sql.db.factory import create_database_backend
from text_to_sql.mcp.tools import create_mcp_server
from text_to_sql.pipeline.agents.models import QueryClassification
from text_to_sql.pipeline.graph import compile_pipeline
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.store.memory import InMemoryQueryStore
from text_to_sql.store.session import InMemorySessionStore

_SIMPLE = {"QueryClassification": QueryClassification(query_type="simple", reasoning="test")}


async def _make_mcp_server(responses: list[AIMessage]):
    """Create a FastMCP server wired to a FakeToolChatModel with the given responses."""
    from text_to_sql.config import Settings

    settings = Settings(_env_file=None)
    db_backend = await create_database_backend(settings)

    from sqlalchemy import text

    async with db_backend._engine.begin() as conn:
        await conn.execute(
            text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
        )
        await conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Alice')"))
        await conn.execute(text("INSERT INTO users (id, name) VALUES (2, 'Bob')"))

    schema_cache = SchemaCache(ttl_seconds=3600)
    chat_model = FakeToolChatModel(messages=iter(responses), structured_responses=_SIMPLE)
    graph = compile_pipeline(
        db_backend=db_backend,
        schema_cache=schema_cache,
        chat_model=chat_model,
        checkpointer=MemorySaver(),
    )
    session_store = InMemorySessionStore()
    orchestrator = PipelineOrchestrator(
        graph=graph,
        query_store=InMemoryQueryStore(),
        session_store=session_store,
    )

    server = create_mcp_server()
    server.state = SimpleNamespace(orchestrator=orchestrator)
    return server, db_backend


@pytest.fixture
async def mcp_server():
    server, db_backend = await _make_mcp_server(
        make_agent_responses("SELECT count(*) AS total FROM users", "There are 2 users."),
    )
    yield server
    await db_backend.close()


@pytest.fixture
async def mcp_client(mcp_server):
    async with Client(mcp_server) as client:
        yield client


# --- Tool Registration ---


@pytest.mark.asyncio
async def test_mcp_server_registers_all_tools(mcp_server) -> None:
    """MCP server should register all 5 tools with correct names."""
    tools = await mcp_server.get_tools()
    assert set(tools.keys()) == {
        "generate_sql",
        "execute_sql",
        "create_session",
        "query_in_session",
        "get_session_history",
    }


# --- generate_sql tool ---


@pytest.mark.asyncio
async def test_generate_sql_auto_executes_safe_query(mcp_client) -> None:
    """generate_sql with safe SELECT should auto-execute and return results."""
    result = await mcp_client.call_tool(
        "generate_sql", {"question": "How many users are there?"}
    )
    data = result.structured_content
    assert "query_id" in data
    assert "generated_sql" in data
    assert data["approval_status"] == "executed"
    assert data["result"] is not None
    assert data["answer"] is not None
    assert data["message"] == "Query executed successfully."


@pytest.mark.asyncio
async def test_generate_sql_returns_unique_ids(mcp_client) -> None:
    """Each generate_sql call should return a unique query_id."""
    r1 = await mcp_client.call_tool("generate_sql", {"question": "How many users?"})
    r2 = await mcp_client.call_tool("generate_sql", {"question": "List all users"})
    assert r1.structured_content["query_id"] != r2.structured_content["query_id"]


# --- execute_sql tool (requires validation errors to get PENDING status) ---


@pytest.fixture
async def pending_mcp_server():
    """MCP server where LLM returns SQL referencing a nonexistent table (triggers validation errors)."""
    server, db_backend = await _make_mcp_server(
        make_agent_responses("SELECT count(*) FROM nonexistent_table", "There is 1 user."),
    )
    yield server
    await db_backend.close()


@pytest.fixture
async def pending_mcp_client(pending_mcp_server):
    async with Client(pending_mcp_server) as client:
        yield client


@pytest.mark.asyncio
async def test_execute_sql_runs_approved_query(pending_mcp_server, pending_mcp_client) -> None:
    """execute_sql should execute after approving with corrected SQL."""
    gen = await pending_mcp_client.call_tool(
        "generate_sql", {"question": "How many items?"}
    )
    query_id = gen.structured_content["query_id"]
    assert gen.structured_content["approval_status"] == "pending"

    await pending_mcp_server.state.orchestrator.approval_manager.approve(
        query_id, modified_sql="SELECT count(*) FROM users"
    )

    result = await pending_mcp_client.call_tool("execute_sql", {"query_id": query_id})
    data = result.structured_content
    assert data["query_id"] == query_id
    assert data["status"] == "executed"


@pytest.mark.asyncio
async def test_execute_sql_rejects_unapproved_query(pending_mcp_client) -> None:
    """execute_sql should fail for a query that hasn't been approved."""
    gen = await pending_mcp_client.call_tool(
        "generate_sql", {"question": "How many items?"}
    )
    query_id = gen.structured_content["query_id"]
    assert gen.structured_content["approval_status"] == "pending"

    with pytest.raises(Exception, match="must be approved"):
        await pending_mcp_client.call_tool("execute_sql", {"query_id": query_id})


@pytest.mark.asyncio
async def test_execute_sql_includes_analytical_fields(pending_mcp_server, pending_mcp_client) -> None:
    """execute_sql response should include query_type, analysis_plan, analysis_steps."""
    gen = await pending_mcp_client.call_tool(
        "generate_sql", {"question": "How many items?"}
    )
    query_id = gen.structured_content["query_id"]

    await pending_mcp_server.state.orchestrator.approval_manager.approve(
        query_id, modified_sql="SELECT count(*) FROM users"
    )

    result = await pending_mcp_client.call_tool("execute_sql", {"query_id": query_id})
    data = result.structured_content
    assert "query_type" in data
    assert "analysis_plan" in data
    assert "analysis_steps" in data


# --- Session tools ---


@pytest.mark.asyncio
async def test_create_session(mcp_client) -> None:
    """create_session should return a session_id."""
    result = await mcp_client.call_tool("create_session", {})
    data = result.structured_content
    assert "session_id" in data
    assert isinstance(data["session_id"], str)
    assert len(data["session_id"]) > 0


@pytest.mark.asyncio
async def test_query_in_session(mcp_client) -> None:
    """query_in_session should execute a query within a session and return all fields."""
    session = await mcp_client.call_tool("create_session", {})
    session_id = session.structured_content["session_id"]

    result = await mcp_client.call_tool(
        "query_in_session",
        {"question": "How many users are there?", "session_id": session_id},
    )
    data = result.structured_content
    assert "query_id" in data
    assert "generated_sql" in data
    assert data["approval_status"] == "executed"
    assert data["result"] is not None
    assert data["answer"] is not None
    assert "query_type" in data
    assert "analysis_plan" in data
    assert "analysis_steps" in data


@pytest.mark.asyncio
async def test_query_in_session_not_found(mcp_client) -> None:
    """query_in_session with invalid session_id should return an error."""
    result = await mcp_client.call_tool(
        "query_in_session",
        {"question": "How many users?", "session_id": "nonexistent-id"},
    )
    data = result.structured_content
    assert "error" in data
    assert "not found" in data["error"]


@pytest.mark.asyncio
async def test_get_session_history(mcp_client) -> None:
    """get_session_history should return queries made in the session."""
    session = await mcp_client.call_tool("create_session", {})
    session_id = session.structured_content["session_id"]

    await mcp_client.call_tool(
        "query_in_session",
        {"question": "How many users are there?", "session_id": session_id},
    )

    result = await mcp_client.call_tool(
        "get_session_history", {"session_id": session_id}
    )
    data = result.structured_content
    assert data["session_id"] == session_id
    assert data["total"] == 1
    assert len(data["queries"]) == 1
    assert "query_id" in data["queries"][0]
    assert data["queries"][0]["approval_status"] == "executed"


@pytest.mark.asyncio
async def test_get_session_history_not_found(mcp_client) -> None:
    """get_session_history with invalid session_id should return an error."""
    result = await mcp_client.call_tool(
        "get_session_history", {"session_id": "nonexistent-id"}
    )
    data = result.structured_content
    assert "error" in data
    assert "not found" in data["error"]


# --- MCP HTTP endpoint ---


@pytest.mark.asyncio
async def test_mcp_endpoint_responds(app) -> None:
    """The /mcp endpoint should accept POST requests (Streamable HTTP)."""
    transport = ASGITransport(app=app)
    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0.1.0"},
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert response.status_code == 200
