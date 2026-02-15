"""Analysis planner agent — creates multi-step analysis plans."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from text_to_sql.pipeline.agents import extract_user_question
from text_to_sql.pipeline.agents.models import AnalysisPlan
from text_to_sql.pipeline.agents.prompts import PLANNER_PROMPT

logger = structlog.get_logger()


def create_plan_analysis_node(
    chat_model: BaseChatModel,
    invoke_with_retry: Callable,
    max_plan_steps: int = 7,
) -> Callable[..., Any]:
    """Create the analysis planning node."""
    structured_model = chat_model.with_structured_output(AnalysisPlan)

    async def plan_analysis(state: dict) -> dict:
        writer = get_stream_writer()
        writer({"event": "planning_analysis"})

        question = extract_user_question(state["messages"])

        # Extract schema context from the SystemMessage already in state
        schema_context = ""
        for msg in state["messages"]:
            if isinstance(msg, SystemMessage):
                schema_context = str(msg.content)
                break

        prompt = PLANNER_PROMPT.format(
            question=question,
            schema_context=schema_context,
            max_plan_steps=max_plan_steps,
        )
        result = await invoke_with_retry(
            structured_model, [HumanMessage(content=prompt)]
        )

        # Truncate to max steps
        steps = result.steps[:max_plan_steps]
        plan = [
            {
                "description": step.description,
                "sql_hint": step.sql_hint,
                "purpose": step.purpose,
            }
            for step in steps
        ]

        logger.info("analysis_plan_created", step_count=len(plan))
        writer({
            "event": "analysis_plan_created",
            "step_count": len(plan),
            "steps": [s["description"] for s in plan],
        })

        return {
            "analysis_plan": plan,
            "plan_results": [],
            "current_step": 0,
        }

    return plan_analysis
