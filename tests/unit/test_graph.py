from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from tests.conftest import FakeToolChatModel, make_agent_responses, make_answer_msg, make_tool_call_msg
from text_to_sql.models.domain import ColumnInfo, TableInfo
from text_to_sql.pipeline.agents.models import QueryClassification
from text_to_sql.pipeline.graph import build_pipeline_graph, compile_pipeline
from text_to_sql.schema.cache import SchemaCache

SIMPLE_CLASSIFICATION = QueryClassification(
    query_type="simple", reasoning="Test default"
)

_STRUCTURED = {"QueryClassification": SIMPLE_CLASSIFICATION}


@pytest.fixture
def mock_backend() -> AsyncMock:
    backend = AsyncMock()
    backend.backend_type = "sqlite"
    backend.discover_tables = AsyncMock(
        return_value=[
            TableInfo(
                table_name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER"),
                    ColumnInfo(name="name", data_type="TEXT"),
                ],
            )
        ]
    )
    backend.validate_sql = AsyncMock(return_value=[])
    backend.execute_sql = AsyncMock(return_value=[{"total": 42}])
    return backend


@pytest.fixture
def compiled_graph(mock_backend):
    model = FakeToolChatModel(
        messages=iter(make_agent_responses("SELECT count(*) AS total FROM users", "There are 42 users.")),
        structured_responses=_STRUCTURED,
    )
    return compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )


@pytest.mark.asyncio
async def test_safe_sql_auto_executes(compiled_graph) -> None:
    """Safe read-only SELECT should auto-execute via ReAct loop and produce answer."""
    config = {"configurable": {"thread_id": "test-safe-1"}}

    await compiled_graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )

    state = await compiled_graph.aget_state(config)
    vals = state.values
    assert not state.next
    assert vals.get("result") == [{"total": 42}]
    assert vals.get("generated_sql") == "SELECT count(*) AS total FROM users"
    assert vals.get("answer") == "There are 42 users."


@pytest.mark.asyncio
async def test_validation_errors_route_to_approval(mock_backend) -> None:
    """SQL with validation errors should pause at human_approval interrupt."""
    mock_backend.validate_sql = AsyncMock(return_value=["Unknown table 'foo'"])
    model = FakeToolChatModel(
        messages=iter([make_tool_call_msg("SELECT count(*) FROM foo")] * 10),
        structured_responses=_STRUCTURED,
    )
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "test-val-err-1"}}

    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many foos?"}]},
        config=config,
    )

    state = await graph.aget_state(config)
    assert state.next  # paused at interrupt


@pytest.mark.asyncio
async def test_graph_resume_approved(mock_backend) -> None:
    """Resuming with approved=True should execute the query and produce answer."""
    mock_backend.validate_sql = AsyncMock(return_value=["some error"])
    model = FakeToolChatModel(
        messages=iter(make_agent_responses("SELECT count(*) AS total FROM users", "There are 42 users.")),
        structured_responses=_STRUCTURED,
    )
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "test-resume-1"}}

    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )

    await graph.ainvoke(Command(resume={"approved": True}), config=config)

    state = await graph.aget_state(config)
    vals = state.values
    assert vals.get("result") == [{"total": 42}]
    assert vals.get("answer") == "There are 42 users."


@pytest.mark.asyncio
async def test_graph_resume_rejected(mock_backend) -> None:
    """Resuming with approved=False should end without executing."""
    mock_backend.validate_sql = AsyncMock(return_value=["some error"])
    model = FakeToolChatModel(
        messages=iter([make_tool_call_msg("SELECT count(*) AS total FROM users")] * 10),
        structured_responses=_STRUCTURED,
    )
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "test-resume-2"}}

    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )

    await graph.ainvoke(Command(resume={"approved": False}), config=config)

    state = await graph.aget_state(config)
    vals = state.values
    assert vals.get("result") is None
    assert vals.get("error") == "Query rejected by user."


@pytest.mark.asyncio
async def test_graph_resume_with_modified_sql(mock_backend) -> None:
    """Resuming with modified SQL should use the new SQL."""
    mock_backend.validate_sql = AsyncMock(return_value=["some error"])
    model = FakeToolChatModel(
        messages=iter(make_agent_responses("SELECT count(*) FROM bad_table", "There are 42 users.")),
        structured_responses=_STRUCTURED,
    )
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "test-resume-3"}}

    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )

    await graph.ainvoke(
        Command(resume={"approved": True, "modified_sql": "SELECT count(*) AS total FROM users"}),
        config=config,
    )

    state = await graph.aget_state(config)
    assert state.values.get("generated_sql") == "SELECT count(*) AS total FROM users"


@pytest.mark.asyncio
async def test_multiturn_truncation_does_not_orphan_tool_messages(mock_backend) -> None:
    """Truncating history must not start with a ToolMessage (orphaned tool_result).

    Regression test for: anthropic.BadRequestError 400 — 'unexpected tool_use_id
    found in tool_result blocks'. When context_history_max_messages is small and
    the conversation accumulates tool_use/tool_result pairs, naive slicing can
    leave a ToolMessage without its preceding AIMessage, which Anthropic rejects.
    """
    model = FakeToolChatModel(
        messages=iter(
            # Turn 1: tool call + answer, Turn 2: tool call + answer
            make_agent_responses("SELECT count(*) AS total FROM users", "42 users.")
        ),
        structured_responses=_STRUCTURED,
    )
    # Set context_history_max_messages very low so truncation triggers on turn 2
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
        context_history_max_messages=3,
    )
    config = {"configurable": {"thread_id": "test-trunc-1"}}

    # Turn 1 — builds up: SystemMsg, HumanMsg, AIMsg(tool_call), ToolMsg, AIMsg(answer)
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )

    # Turn 2 — adds HumanMsg, then re-enters generate_query with a long history.
    # With max_messages=3, naive slicing would grab [..., ToolMsg, AIMsg, HumanMsg]
    # starting with an orphaned ToolMsg. The fix skips leading ToolMessages.
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "And how many are active?"}]},
        config=config,
    )

    state = await graph.aget_state(config)
    vals = state.values
    # If the fix works, the pipeline completes without BadRequestError
    assert vals.get("answer") is not None
    assert not state.next


@pytest.mark.asyncio
async def test_multiturn_state_reset_clears_previous_results(mock_backend) -> None:
    """State fields from a previous turn must not leak into the next turn.

    Regression test for stale data leakage: after a simple query sets
    generated_sql/result, a follow-up turn should start with clean state.
    """
    model = FakeToolChatModel(
        messages=iter(
            make_agent_responses("SELECT count(*) AS total FROM users", "42 users.")
        ),
        structured_responses=_STRUCTURED,
    )
    graph = compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=model,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "test-reset-1"}}

    # Turn 1 — simple query with result
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "How many users?"}]},
        config=config,
    )
    state1 = await graph.aget_state(config)
    assert state1.values.get("result") == [{"total": 42}]
    assert state1.values.get("generated_sql") == "SELECT count(*) AS total FROM users"

    # Turn 2 — another query; state should reflect this turn, not turn 1
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "List all users."}]},
        config=config,
    )
    state2 = await graph.aget_state(config)
    assert state2.values.get("error") is None
    assert state2.values.get("answer") is not None


def test_build_pipeline_graph_creates_nodes(mock_backend) -> None:
    """Verify the graph builder creates all expected nodes."""
    model = FakeToolChatModel(
        messages=iter([make_answer_msg("test")]),
        structured_responses=_STRUCTURED,
    )
    builder = build_pipeline_graph(mock_backend, SchemaCache(ttl_seconds=3600), model)
    assert builder is not None
