"""Tests for the query classifier agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from text_to_sql.pipeline.agents.classifier import create_classify_query_node
from text_to_sql.pipeline.agents.models import QueryClassification


@pytest.fixture
def mock_stream_writer(monkeypatch):
    writer = AsyncMock()
    monkeypatch.setattr(
        "text_to_sql.pipeline.agents.classifier.get_stream_writer",
        lambda: writer,
    )
    return writer


class TestClassifyQueryNode:
    @pytest.mark.asyncio
    async def test_analytical_query_classified(self, mock_stream_writer):
        """Analytical queries should be classified as analytical."""
        classification = QueryClassification(
            query_type="analytical",
            reasoning="Multi-step analysis needed",
        )

        mock_model = AsyncMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=classification)
        mock_model.with_structured_output = lambda schema: mock_structured

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_classify_query_node(mock_model, fake_invoke)
        state = {
            "messages": [HumanMessage(content="Analyze sales trends and recommend improvements")],
        }
        result = await node(state)

        assert result["query_type"] == "analytical"

    @pytest.mark.asyncio
    async def test_simple_query_classified(self, mock_stream_writer):
        """Simple queries should be classified as simple."""
        classification = QueryClassification(
            query_type="simple",
            reasoning="Direct count query",
        )

        mock_model = AsyncMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=classification)
        mock_model.with_structured_output = lambda schema: mock_structured

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_classify_query_node(mock_model, fake_invoke)
        state = {
            "messages": [HumanMessage(content="How many users are there?")],
        }
        result = await node(state)

        assert result["query_type"] == "simple"

    @pytest.mark.asyncio
    async def test_llm_failure_defaults_to_simple(self, mock_stream_writer):
        """On LLM failure, classifier should default to simple."""
        mock_model = AsyncMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_model.with_structured_output = lambda schema: mock_structured

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_classify_query_node(mock_model, fake_invoke)
        state = {
            "messages": [HumanMessage(content="Analyze everything")],
        }
        result = await node(state)

        assert result["query_type"] == "simple"

    @pytest.mark.asyncio
    async def test_empty_messages_defaults_to_simple(self, mock_stream_writer):
        """No messages should default to simple."""
        mock_model = AsyncMock()

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_classify_query_node(mock_model, fake_invoke)
        state = {"messages": []}
        result = await node(state)

        assert result["query_type"] == "simple"
