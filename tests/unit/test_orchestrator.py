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
    """
    graph = MagicMock()

    graph.ainvoke = AsyncMock(return_value=None)

    mock_state = MagicMock()
    mock_state.values = {
        "messages": [],
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [] if completed else ["Unknown table"],
        "result": [{"total": 42}] if completed else None,
        "answer": "There are 42 users." if completed else None,
        "error": None,
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
    assert record.answer == "There are 42 users."
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

    # After resume, mock graph returns completed state
    completed_state = MagicMock()
    completed_state.values = {
        "messages": [],
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "result": [{"total": 42}],
        "answer": "There are 42 users.",
        "error": None,
    }
    completed_state.next = ()
    orchestrator_pending._graph.aget_state = AsyncMock(return_value=completed_state)

    executed = await orchestrator_pending.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.EXECUTED
    assert executed.result == [{"total": 42}]
    assert executed.answer == "There are 42 users."


@pytest.mark.asyncio
async def test_execute_unapproved_raises(orchestrator_pending: PipelineOrchestrator) -> None:
    record = await orchestrator_pending.submit_question("How many users?")
    with pytest.raises(ValueError, match="must be approved"):
        await orchestrator_pending.execute_approved(record.id)


@pytest.mark.asyncio
async def test_auto_execute_failure_marks_failed() -> None:
    """If auto-execute returns an error, status should be FAILED."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=None)
    mock_state = MagicMock()
    mock_state.values = {
        "messages": [],
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "result": None,
        "answer": None,
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
async def test_execute_failure_marks_failed() -> None:
    """If execution after approval returns an error, status should be FAILED."""
    # First call: pending (validation errors)
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=None)

    pending_state = MagicMock()
    pending_state.values = {
        "messages": [],
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": ["Unknown table"],
        "result": None,
        "answer": None,
        "error": None,
    }
    pending_state.next = ("human_approval",)

    failed_state = MagicMock()
    failed_state.values = {
        "messages": [],
        "generated_sql": "SELECT count(*) AS total FROM users",
        "validation_errors": [],
        "result": None,
        "answer": None,
        "error": "DB error",
    }
    failed_state.next = ()

    graph.aget_state = AsyncMock(side_effect=[pending_state, failed_state])

    orchestrator = PipelineOrchestrator(
        graph=graph,
        query_store=InMemoryQueryStore(),
    )
    record = await orchestrator.submit_question("How many users?")
    await orchestrator.approval_manager.approve(record.id)
    executed = await orchestrator.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.FAILED
    assert "DB error" in executed.error
