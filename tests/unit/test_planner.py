"""Tests for the analysis planner agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from text_to_sql.pipeline.agents.models import AnalysisPlan, AnalysisStep
from text_to_sql.pipeline.agents.planner import create_plan_analysis_node


@pytest.fixture
def mock_stream_writer(monkeypatch):
    writer = AsyncMock()
    monkeypatch.setattr(
        "text_to_sql.pipeline.agents.planner.get_stream_writer",
        lambda: writer,
    )
    return writer


class TestPlanAnalysisNode:
    @pytest.mark.asyncio
    async def test_creates_plan_with_steps(self, mock_stream_writer):
        """Planner should create a structured plan with steps."""
        plan = AnalysisPlan(
            steps=[
                AnalysisStep(
                    description="Get total sales by month",
                    sql_hint="SELECT month, SUM(amount) FROM sales GROUP BY month",
                    purpose="Identify monthly trends",
                ),
                AnalysisStep(
                    description="Get top products by revenue",
                    sql_hint="SELECT product, SUM(revenue) FROM sales GROUP BY product ORDER BY 2 DESC",
                    purpose="Find best performers",
                ),
            ],
            synthesis_guidance="Compare trends with product performance",
        )

        mock_model = AsyncMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=plan)
        mock_model.with_structured_output = lambda schema: mock_structured

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_plan_analysis_node(mock_model, fake_invoke, max_plan_steps=7)
        state = {
            "messages": [
                SystemMessage(content="Schema: CREATE TABLE sales (...)"),
                HumanMessage(content="Analyze sales trends"),
            ],
        }
        result = await node(state)

        assert len(result["analysis_plan"]) == 2
        assert result["plan_results"] == []
        assert result["current_step"] == 0
        assert result["analysis_plan"][0]["description"] == "Get total sales by month"

    @pytest.mark.asyncio
    async def test_truncates_to_max_steps(self, mock_stream_writer):
        """Planner should truncate steps to max_plan_steps."""
        steps = [
            AnalysisStep(
                description=f"Step {i}",
                sql_hint=f"SELECT {i}",
                purpose=f"Purpose {i}",
            )
            for i in range(10)
        ]
        plan = AnalysisPlan(steps=steps[:7], synthesis_guidance="Combine")

        mock_model = AsyncMock()
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=plan)
        mock_model.with_structured_output = lambda schema: mock_structured

        async def fake_invoke(model, messages):
            return await model.ainvoke(messages)

        node = create_plan_analysis_node(mock_model, fake_invoke, max_plan_steps=3)
        state = {
            "messages": [
                SystemMessage(content="Schema"),
                HumanMessage(content="Analyze everything"),
            ],
        }
        result = await node(state)

        assert len(result["analysis_plan"]) == 3
