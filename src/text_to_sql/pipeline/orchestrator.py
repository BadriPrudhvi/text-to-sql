from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from langgraph.types import Command

from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.pipeline.approval import ApprovalManager
from text_to_sql.store.base import QueryStore

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Coordinates the full NL -> SQL -> Approval -> Execution pipeline via LangGraph."""

    def __init__(
        self,
        graph: Any,
        query_store: QueryStore,
    ) -> None:
        self._graph = graph
        self._store = query_store
        self._approval_manager = ApprovalManager(query_store)

    @property
    def approval_manager(self) -> ApprovalManager:
        return self._approval_manager

    async def submit_question(self, question: str) -> QueryRecord:
        """Run the LangGraph pipeline. Safe read-only queries auto-execute; unsafe ones pause for approval."""
        record = QueryRecord(
            natural_language=question,
            database_type="",
        )

        config = {"configurable": {"thread_id": record.id}}

        await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )

        state = await self._graph.aget_state(config)
        graph_state = state.values

        record.generated_sql = graph_state.get("generated_sql") or ""
        record.validation_errors = graph_state.get("validation_errors", [])

        if not state.next:
            # Graph ran to completion — query was auto-executed
            if graph_state.get("error"):
                record.error = graph_state["error"]
                record.approval_status = ApprovalStatus.FAILED
            else:
                record.result = graph_state.get("result")
                record.answer = graph_state.get("answer")
                record.approval_status = ApprovalStatus.EXECUTED
                record.executed_at = datetime.now(timezone.utc)
            await self._store.save(record)
        else:
            # Graph paused at human_approval interrupt
            record = await self._approval_manager.submit_for_approval(record)

        logger.info(
            "question_submitted",
            query_id=record.id,
            question=question,
            sql=record.generated_sql,
            status=record.approval_status.value,
        )
        return record

    async def execute_approved(self, query_id: str) -> QueryRecord:
        """Phase 2: Resume the LangGraph pipeline after human approval."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.APPROVED:
            raise ValueError(
                f"Query {query_id} must be approved before execution "
                f"(current status: {record.approval_status.value})"
            )

        config = {"configurable": {"thread_id": query_id}}

        # Resume the graph from the interrupt with approval decision
        resume_value: dict[str, Any] = {"approved": True}
        if record.generated_sql:
            resume_value["modified_sql"] = record.generated_sql

        await self._graph.ainvoke(
            Command(resume=resume_value),
            config=config,
        )

        # Read final state after graph completes
        state = await self._graph.aget_state(config)
        result = state.values

        if result.get("error"):
            record.error = result["error"]
            record.approval_status = ApprovalStatus.FAILED
            logger.error("query_execution_failed", query_id=query_id, error=record.error)
        else:
            record.result = result.get("result")
            record.answer = result.get("answer")
            record.generated_sql = result.get("generated_sql") or record.generated_sql
            record.approval_status = ApprovalStatus.EXECUTED
            record.executed_at = datetime.now(timezone.utc)
            logger.info(
                "query_executed",
                query_id=query_id,
                row_count=len(record.result) if record.result else 0,
            )

        await self._store.save(record)
        return record
