from __future__ import annotations

import pytest

from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.pipeline.approval import ApprovalManager
from text_to_sql.store.memory import InMemoryQueryStore


@pytest.fixture
def store() -> InMemoryQueryStore:
    return InMemoryQueryStore()


@pytest.fixture
def manager(store: InMemoryQueryStore) -> ApprovalManager:
    return ApprovalManager(query_store=store)


@pytest.mark.asyncio
async def test_submit_for_approval(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    result = await manager.submit_for_approval(record)
    assert result.approval_status == ApprovalStatus.PENDING


@pytest.mark.asyncio
async def test_approve(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    await manager.submit_for_approval(record)
    approved = await manager.approve(record.id)
    assert approved.approval_status == ApprovalStatus.APPROVED
    assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_approve_with_modified_sql(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    await manager.submit_for_approval(record)
    approved = await manager.approve(record.id, modified_sql="SELECT 2")
    assert approved.generated_sql == "SELECT 2"


@pytest.mark.asyncio
async def test_reject(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    await manager.submit_for_approval(record)
    rejected = await manager.reject(record.id)
    assert rejected.approval_status == ApprovalStatus.REJECTED


@pytest.mark.asyncio
async def test_approve_non_pending_raises(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    await manager.submit_for_approval(record)
    await manager.approve(record.id)
    with pytest.raises(ValueError, match="not pending"):
        await manager.approve(record.id)


@pytest.mark.asyncio
async def test_reject_non_pending_raises(manager: ApprovalManager) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        generated_sql="SELECT 1",
    )
    await manager.submit_for_approval(record)
    await manager.reject(record.id)
    with pytest.raises(ValueError, match="not pending"):
        await manager.reject(record.id)
