"""Tests for the analysis validator agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from text_to_sql.pipeline.agents.analysis_validator import (
    create_validate_analysis_node,
)


@pytest.fixture
def mock_stream_writer(monkeypatch):
    writer = AsyncMock()
    monkeypatch.setattr(
        "text_to_sql.pipeline.agents.analysis_validator.get_stream_writer",
        lambda: writer,
    )
    return writer


class TestValidateAnalysisNode:
    @pytest.mark.asyncio
    async def test_passes_with_good_results(self, mock_stream_writer):
        """Validation should pass when results are complete and relevant."""
        node = create_validate_analysis_node(max_synthesis_attempts=1)
        state = {
            "messages": [HumanMessage(content="Analyze user data")],
            "plan_results": [
                {"description": "Count users", "sql": "SELECT count(*)", "result": [{"count": 100}], "error": None},
                {"description": "User stats", "sql": "SELECT avg(age)", "result": [{"avg": 30}], "error": None},
            ],
            "answer": "Based on the user data analysis, there are 100 users with an average age of 30. "
                     "The data shows a healthy user base with consistent engagement patterns.",
            "synthesis_attempts": 1,
        }
        result = await node(state)

        # No revision HumanMessage added = validation passed
        assert "messages" not in result or not result.get("messages")

    @pytest.mark.asyncio
    async def test_warns_on_high_failure_rate(self, mock_stream_writer):
        """Validation should warn when >50% steps failed."""
        node = create_validate_analysis_node(max_synthesis_attempts=2)
        state = {
            "messages": [HumanMessage(content="Analyze user data")],
            "plan_results": [
                {"description": "Step 1", "sql": "SELECT 1", "result": None, "error": "timeout"},
                {"description": "Step 2", "sql": "SELECT 2", "result": None, "error": "timeout"},
                {"description": "Step 3", "sql": "SELECT 3", "result": [{"x": 1}], "error": None},
            ],
            "answer": "Some analysis here about user data and findings.",
            "synthesis_attempts": 0,
        }
        result = await node(state)

        # Should add revision guidance
        assert result.get("messages")
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "revise" in msg.content.lower()

    @pytest.mark.asyncio
    async def test_no_revision_at_max_attempts(self, mock_stream_writer):
        """Should not request revision when at max synthesis attempts."""
        node = create_validate_analysis_node(max_synthesis_attempts=1)
        state = {
            "messages": [HumanMessage(content="Analyze user data")],
            "plan_results": [
                {"description": "Step 1", "sql": "SELECT 1", "result": None, "error": "timeout"},
                {"description": "Step 2", "sql": "SELECT 2", "result": None, "error": "timeout"},
            ],
            "answer": "Limited analysis due to data issues about user data.",
            "synthesis_attempts": 1,
        }
        result = await node(state)

        # At max attempts, should not request revision
        assert not result.get("messages")

    @pytest.mark.asyncio
    async def test_warns_on_brief_answer(self, mock_stream_writer):
        """Should warn when answer is too brief for successful steps."""
        node = create_validate_analysis_node(max_synthesis_attempts=2)
        state = {
            "messages": [HumanMessage(content="Analyze user data trends")],
            "plan_results": [
                {"description": "Step 1", "sql": "SELECT 1", "result": [{"x": 1}], "error": None},
                {"description": "Step 2", "sql": "SELECT 2", "result": [{"y": 2}], "error": None},
                {"description": "Step 3", "sql": "SELECT 3", "result": [{"z": 3}], "error": None},
            ],
            "answer": "OK",
            "synthesis_attempts": 0,
        }
        result = await node(state)

        assert result.get("messages")
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)

    @pytest.mark.asyncio
    async def test_passes_empty_plan(self, mock_stream_writer):
        """Should pass gracefully with no plan results."""
        node = create_validate_analysis_node(max_synthesis_attempts=1)
        state = {
            "messages": [HumanMessage(content="Analyze")],
            "plan_results": [],
            "answer": "No data available for analysis.",
            "synthesis_attempts": 1,
        }
        result = await node(state)
        assert not result.get("messages")
