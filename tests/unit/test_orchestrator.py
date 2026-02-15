from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from text_to_sql.models.domain import ApprovalStatus
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.store.memory import InMemoryQueryStore


def _make_mock_graph(*, completed: bool = True) -> MagicMock:
    """Create a mock LangGraph compiled graph.

    Args:
        completed: If True, graph ran to completion (auto-executed).
                   If False, graph paused at interrupt (validation errors).
                   Resume call always returns results.
    """
    graph = MagicMock()

    # ainvoke returns results on every call (including resume)
    graph.ainvoke = AsyncMock(return_value={
        "question": "How many users?",
        "dialect": "sqlite",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [] if completed else ["Unknown table"],
        "result": [{"total": 42}],
    })

    mock_state = MagicMock()
    mock_state.values = {
        "question": "How many users?",
        "dialect": "sqlite",
        "schema_context": "CREATE TABLE users (...)",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [] if completed else ["Unknown table"],
        "result": [{"total": 42}] if completed else None,
    }
    mock_state.next = () if completed else ("human_approval",)
    graph.aget_state = AsyncMock(return_value=mock_state)

    return graph


@pytest.fixture
def mock_graph() -> MagicMock:
    return _make_mock_graph(completed=True)


@pytest.fixture
def mock_graph_pending() -> MagicMock:
    return _make_mock_graph(completed=False)


@pytest.fixture
def orchestrator(mock_graph: MagicMock) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        graph=mock_graph,
        query_store=InMemoryQueryStore(),
    )


@pytest.fixture
def orchestrator_pending(mock_graph_pending: MagicMock) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        graph=mock_graph_pending,
        query_store=InMemoryQueryStore(),
    )


@pytest.mark.asyncio
async def test_submit_question_auto_executes(orchestrator: PipelineOrchestrator) -> None:
    """Valid SQL should auto-execute and return EXECUTED status with results."""
    record = await orchestrator.submit_question("How many users?")
    assert record.natural_language == "How many users?"
    assert record.generated_sql == "SELECT count(*) AS total FROM users"
    assert record.approval_status == ApprovalStatus.EXECUTED
    assert record.result == [{"total": 42}]
    assert record.executed_at is not None


@pytest.mark.asyncio
async def test_submit_question_with_validation_errors_pending(
    orchestrator_pending: PipelineOrchestrator,
) -> None:
    """SQL with validation errors should pause and return PENDING status."""
    record = await orchestrator_pending.submit_question("How many users?")
    assert record.approval_status == ApprovalStatus.PENDING
    assert record.result is None


@pytest.mark.asyncio
async def test_execute_approved(orchestrator_pending: PipelineOrchestrator) -> None:
    record = await orchestrator_pending.submit_question("How many users?")
    await orchestrator_pending.approval_manager.approve(record.id)
    executed = await orchestrator_pending.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.EXECUTED
    assert executed.result == [{"total": 42}]


@pytest.mark.asyncio
async def test_execute_unapproved_raises(orchestrator_pending: PipelineOrchestrator) -> None:
    record = await orchestrator_pending.submit_question("How many users?")
    with pytest.raises(ValueError, match="must be approved"):
        await orchestrator_pending.execute_approved(record.id)


@pytest.mark.asyncio
async def test_auto_execute_failure_marks_failed() -> None:
    """If auto-execute returns an error, status should be FAILED."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={
        "dialect": "sqlite",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "error": "DB error",
    })
    mock_state = MagicMock()
    mock_state.values = {
        "dialect": "sqlite",
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "error": "DB error",
    }
    mock_state.next = ()
    graph.aget_state = AsyncMock(return_value=mock_state)

    orchestrator = PipelineOrchestrator(
        graph=graph,
        query_store=InMemoryQueryStore(),
    )
    record = await orchestrator.submit_question("How many users?")
    assert record.approval_status == ApprovalStatus.FAILED
    assert record.error == "DB error"


@pytest.mark.asyncio
async def test_execute_failure_marks_failed(mock_graph_pending: MagicMock) -> None:
    """If execution after approval returns an error, status should be FAILED."""
    call_count = 0
    original_ainvoke = mock_graph_pending.ainvoke

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await original_ainvoke(*args, **kwargs)
        else:
            return {
                "generated_sql": "SELECT count(*) AS total FROM users",
                "error": "DB error",
            }

    mock_graph_pending.ainvoke = AsyncMock(side_effect=side_effect)
    orchestrator = PipelineOrchestrator(
        graph=mock_graph_pending,
        query_store=InMemoryQueryStore(),
    )
    record = await orchestrator.submit_question("How many users?")
    await orchestrator.approval_manager.approve(record.id)
    executed = await orchestrator.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.FAILED
    assert "DB error" in executed.error
