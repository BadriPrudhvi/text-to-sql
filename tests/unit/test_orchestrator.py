from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from text_to_sql.config import Settings
from text_to_sql.models.domain import ApprovalStatus, ColumnInfo, TableInfo
from text_to_sql.pipeline.orchestrator import PipelineOrchestrator
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.store.memory import InMemoryQueryStore


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
def mock_router() -> MagicMock:
    router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT count(*) AS total FROM users"
    mock_response.model = "test-model"
    router.acompletion = AsyncMock(return_value=mock_response)
    return router


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    return Settings()


@pytest.fixture
def orchestrator(
    mock_backend: AsyncMock,
    mock_router: MagicMock,
    settings: Settings,
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        db_backend=mock_backend,
        schema_cache=SchemaCache(ttl_seconds=3600),
        llm_router=mock_router,
        query_store=InMemoryQueryStore(),
        settings=settings,
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
async def test_execute_failure_marks_failed(
    orchestrator: PipelineOrchestrator, mock_backend: AsyncMock
) -> None:
    mock_backend.execute_sql = AsyncMock(side_effect=RuntimeError("DB error"))
    record = await orchestrator.submit_question("How many users?")
    await orchestrator.approval_manager.approve(record.id)
    executed = await orchestrator.execute_approved(record.id)
    assert executed.approval_status == ApprovalStatus.FAILED
    assert "DB error" in executed.error
