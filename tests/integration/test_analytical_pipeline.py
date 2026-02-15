"""Integration tests for the multi-agent analytical query pipeline."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import text

from tests.conftest import FakeToolChatModel, make_agent_responses
from text_to_sql.db.sqlite import SqliteBackend
from text_to_sql.pipeline.agents.models import (
    AnalysisPlan,
    AnalysisStep,
    QueryClassification,
)
from text_to_sql.pipeline.graph import compile_pipeline
from text_to_sql.schema.cache import SchemaCache


async def _create_test_backend():
    """Create an in-memory SQLite backend with a users table."""
    backend = SqliteBackend("sqlite+aiosqlite://")
    await backend.connect()
    async with backend._engine.begin() as conn:
        await conn.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        )
        await conn.execute(text("INSERT INTO users VALUES (1, 'Alice')"))
        await conn.execute(text("INSERT INTO users VALUES (2, 'Bob')"))
    return backend


class TestAnalyticalPipelineIntegration:
    @pytest.mark.asyncio
    async def test_simple_query_bypasses_analytical_path(self):
        """Simple queries should flow through the existing simple path."""
        classification = QueryClassification(
            query_type="simple", reasoning="Direct count"
        )
        model = FakeToolChatModel(
            messages=iter(make_agent_responses(
                "SELECT count(*) AS total FROM users", "There are 2 users."
            )),
            structured_responses={"QueryClassification": classification},
        )

        backend = await _create_test_backend()
        graph = compile_pipeline(
            db_backend=backend,
            schema_cache=SchemaCache(ttl_seconds=3600),
            chat_model=model,
            checkpointer=MemorySaver(),
        )

        config = {"configurable": {"thread_id": "test-simple"}}
        events = []
        async for chunk in graph.astream(
            {"messages": [HumanMessage(content="How many users?")]},
            config=config,
            stream_mode="custom",
        ):
            events.append(chunk)

        await backend.close()

        event_types = [e.get("event") for e in events if isinstance(e, dict)]
        assert "query_classified" in event_types
        assert "planning_analysis" not in event_types

    @pytest.mark.asyncio
    async def test_analytical_query_full_flow(self):
        """Analytical queries should plan, execute steps, and synthesize."""
        classification = QueryClassification(
            query_type="analytical", reasoning="Multi-step analysis"
        )
        plan = AnalysisPlan(
            steps=[
                AnalysisStep(
                    description="Count users",
                    sql_hint="SELECT count(*) FROM users",
                    purpose="Get baseline count",
                ),
                AnalysisStep(
                    description="Average age",
                    sql_hint="SELECT avg(age) FROM users",
                    purpose="Understand demographics",
                ),
            ],
            synthesis_guidance="Combine user count with age data",
        )

        model = FakeToolChatModel(
            messages=iter([
                AIMessage(content="SELECT count(*) AS total FROM users"),
                AIMessage(content="SELECT name, 30 AS age FROM users"),
                AIMessage(
                    content="Analysis complete: There are 2 users. "
                    "The average user profile shows active engagement. "
                    "Recommendations: Focus on user retention and growth strategies."
                ),
            ]),
            structured_responses={
                "QueryClassification": classification,
                "AnalysisPlan": plan,
            },
        )

        backend = await _create_test_backend()
        graph = compile_pipeline(
            db_backend=backend,
            schema_cache=SchemaCache(ttl_seconds=3600),
            chat_model=model,
            checkpointer=MemorySaver(),
        )

        config = {"configurable": {"thread_id": "test-analytical"}}
        events = []
        async for chunk in graph.astream(
            {"messages": [HumanMessage(content="Analyze user data and recommend improvements")]},
            config=config,
            stream_mode="custom",
        ):
            events.append(chunk)

        await backend.close()

        event_types = [e.get("event") for e in events if isinstance(e, dict)]
        assert "query_classified" in event_types
        assert "planning_analysis" in event_types
        assert "analysis_plan_created" in event_types
        assert "plan_step_started" in event_types
        assert "analysis_complete" in event_types

    @pytest.mark.asyncio
    async def test_analytical_with_step_failure(self):
        """Analysis should handle partial step failures gracefully."""
        classification = QueryClassification(
            query_type="analytical", reasoning="Analysis needed"
        )
        plan = AnalysisPlan(
            steps=[
                AnalysisStep(
                    description="Valid query",
                    sql_hint="SELECT count(*) FROM users",
                    purpose="Get count",
                ),
                AnalysisStep(
                    description="Bad query",
                    sql_hint="SELECT FROM nonexistent",
                    purpose="This will fail",
                ),
            ],
            synthesis_guidance="Work with available data",
        )

        model = FakeToolChatModel(
            messages=iter([
                AIMessage(content="SELECT count(*) AS total FROM users"),
                AIMessage(content="SELECT * FROM nonexistent_table"),
                AIMessage(
                    content="Based on available data: 2 users found. "
                    "Some analysis steps failed but core user data indicates "
                    "a growing user base with recommendations for expansion."
                ),
            ]),
            structured_responses={
                "QueryClassification": classification,
                "AnalysisPlan": plan,
            },
        )

        backend = await _create_test_backend()
        graph = compile_pipeline(
            db_backend=backend,
            schema_cache=SchemaCache(ttl_seconds=3600),
            chat_model=model,
            checkpointer=MemorySaver(),
        )

        config = {"configurable": {"thread_id": "test-failure"}}
        events = []
        async for chunk in graph.astream(
            {"messages": [HumanMessage(content="Analyze user patterns")]},
            config=config,
            stream_mode="custom",
        ):
            events.append(chunk)

        await backend.close()

        event_types = [e.get("event") for e in events if isinstance(e, dict)]
        assert "analysis_complete" in event_types
        assert "plan_step_failed" in event_types or "plan_step_executed" in event_types

    @pytest.mark.asyncio
    async def test_streaming_events_include_new_types(self):
        """Verify all new analytical event types are emitted."""
        classification = QueryClassification(
            query_type="analytical", reasoning="Analysis"
        )
        plan = AnalysisPlan(
            steps=[
                AnalysisStep(
                    description="Single step",
                    sql_hint="SELECT 1",
                    purpose="Test",
                ),
            ],
            synthesis_guidance="Summarize",
        )

        model = FakeToolChatModel(
            messages=iter([
                AIMessage(content="SELECT count(*) FROM users"),
                AIMessage(
                    content="Comprehensive analysis of user data shows 2 users with "
                    "active engagement patterns and recommendations for growth."
                ),
            ]),
            structured_responses={
                "QueryClassification": classification,
                "AnalysisPlan": plan,
            },
        )

        backend = await _create_test_backend()
        graph = compile_pipeline(
            db_backend=backend,
            schema_cache=SchemaCache(ttl_seconds=3600),
            chat_model=model,
            checkpointer=MemorySaver(),
        )

        config = {"configurable": {"thread_id": "test-events"}}
        events = []
        async for chunk in graph.astream(
            {"messages": [HumanMessage(content="Analyze user engagement")]},
            config=config,
            stream_mode="custom",
        ):
            events.append(chunk)

        await backend.close()

        event_types = [e.get("event") for e in events if isinstance(e, dict)]
        expected_events = [
            "schema_discovery_started",
            "schema_discovered",
            "classifying_query",
            "query_classified",
            "planning_analysis",
            "analysis_plan_created",
            "plan_step_started",
            "analysis_synthesis_started",
            "analysis_complete",
        ]
        for expected in expected_events:
            assert expected in event_types, f"Missing event: {expected}"
