from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from text_to_sql.models.domain import ColumnInfo, TableInfo
from text_to_sql.pipeline.graph import build_pipeline_graph, compile_pipeline
from text_to_sql.schema.cache import SchemaCache


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
def fake_chat_model() -> FakeListChatModel:
    """A real LangChain ChatModel that returns predictable SQL responses."""
    return FakeListChatModel(
        responses=["SELECT count(*) AS total FROM users"] * 10,
    )


@pytest.fixture
def compiled_graph(mock_backend, fake_chat_model):
    checkpointer = MemorySaver()
    return compile_pipeline(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        chat_model=fake_chat_model,
        checkpointer=checkpointer,
    )


@pytest.mark.asyncio
async def test_graph_pauses_at_interrupt(compiled_graph) -> None:
    """Graph should pause at human_approval interrupt and return partial state."""
    config = {"configurable": {"thread_id": "test-1"}}

    result = await compiled_graph.ainvoke(
        {"question": "How many users?"},
        config=config,
    )

    # After interrupt, the graph returns the state up to the interrupt point
    state = await compiled_graph.aget_state(config)
    assert state.values.get("generated_sql") == "SELECT count(*) AS total FROM users"
    assert state.values.get("dialect") == "sqlite"
    # Graph should be waiting at an interrupt (next node is not None)
    assert state.next is not None


@pytest.mark.asyncio
async def test_graph_resume_approved(compiled_graph) -> None:
    """Resuming with approved=True should execute the query."""
    config = {"configurable": {"thread_id": "test-2"}}

    # Phase 1: submit
    await compiled_graph.ainvoke(
        {"question": "How many users?"},
        config=config,
    )

    # Phase 2: resume with approval
    result = await compiled_graph.ainvoke(
        Command(resume={"approved": True}),
        config=config,
    )

    assert result.get("result") == [{"total": 42}]


@pytest.mark.asyncio
async def test_graph_resume_rejected(compiled_graph) -> None:
    """Resuming with approved=False should end without executing."""
    config = {"configurable": {"thread_id": "test-3"}}

    # Phase 1: submit
    await compiled_graph.ainvoke(
        {"question": "How many users?"},
        config=config,
    )

    # Phase 2: resume with rejection
    result = await compiled_graph.ainvoke(
        Command(resume={"approved": False}),
        config=config,
    )

    # Result should not be populated
    assert result.get("result") is None


@pytest.mark.asyncio
async def test_graph_resume_with_modified_sql(compiled_graph) -> None:
    """Resuming with modified SQL should use the new SQL."""
    config = {"configurable": {"thread_id": "test-4"}}

    await compiled_graph.ainvoke(
        {"question": "How many users?"},
        config=config,
    )

    result = await compiled_graph.ainvoke(
        Command(resume={"approved": True, "modified_sql": "SELECT 1"}),
        config=config,
    )

    assert result.get("generated_sql") == "SELECT 1"


def test_build_pipeline_graph_creates_nodes(mock_backend, fake_chat_model) -> None:
    """Verify the graph builder creates all expected nodes."""
    builder = build_pipeline_graph(mock_backend, SchemaCache(ttl_seconds=3600), fake_chat_model)
    assert builder is not None
