from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from text_to_sql.models.domain import ApprovalStatus
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.store.memory import InMemoryQueryStore


@pytest.fixture
def mock_graph() -> MagicMock:
    """Create a mock LangGraph compiled graph."""
    graph = MagicMock()

    # Mock ainvoke — first call pauses at interrupt, second call returns results
    graph.ainvoke = AsyncMock(return_value={
        "question": "How many users?",
        "dialect": "sqlite",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "result": [{"total": 42}],
    })

    # Mock aget_state — returns graph state after interrupt
    mock_state = MagicMock()
    mock_state.values = {
        "question": "How many users?",
        "dialect": "sqlite",
        "schema_context": "CREATE TABLE users (...)",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
    }
    graph.aget_state = AsyncMock(return_value=mock_state)

    return graph


@pytest.fixture
def orchestrator(mock_graph: MagicMock) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        graph=mock_graph,
        query_store=InMemoryQueryStore(),
    )


@pytest.mark.asyncio
async def test_submit_question(orchestrator: PipelineOrchestrator) -> None:
    record = await orchestrator.submit_question("How many users?")
    assert record.natural_language == "How many users?"
    assert record.generated_sql == "SELECT count(*) AS total FROM users"
    assert record.approval_status == ApprovalStatus.PENDING
    assert record.validation_errors == []


@pytest.mark.asyncio
async def test_execute_approved(orchestrator: PipelineOrchestrator) -> None:
    record = await orchestrator.submit_question("How many users?")
    await orchestrator.approval_manager.approve(record.id)
    executed = await orchestrator.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.EXECUTED
    assert executed.result == [{"total": 42}]


@pytest.mark.asyncio
async def test_execute_unapproved_raises(orchestrator: PipelineOrchestrator) -> None:
    record = await orchestrator.submit_question("How many users?")
    with pytest.raises(ValueError, match="must be approved"):
        await orchestrator.execute_approved(record.id)


@pytest.mark.asyncio
async def test_execute_failure_marks_failed(mock_graph: MagicMock) -> None:
    # Configure graph to return an error on resume
    call_count = 0
    original_ainvoke = mock_graph.ainvoke

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: submit question (pauses at interrupt)
            return await original_ainvoke(*args, **kwargs)
        else:
            # Second call: resume returns error
            return {
                "generated_sql": "SELECT count(*) AS total FROM users",
                "error": "DB error",
            }

    mock_graph.ainvoke = AsyncMock(side_effect=side_effect)
    orchestrator = PipelineOrchestrator(
        graph=mock_graph,
        query_store=InMemoryQueryStore(),
    )
    record = await orchestrator.submit_question("How many users?")
    await orchestrator.approval_manager.approve(record.id)
    executed = await orchestrator.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.FAILED
    assert "DB error" in executed.error
