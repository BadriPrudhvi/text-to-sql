"""Analysis validator — deterministic checks on synthesis quality."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer

from text_to_sql.pipeline.agents import extract_user_question

logger = structlog.get_logger()


def create_validate_analysis_node(
    max_synthesis_attempts: int = 1,
) -> Callable[..., Any]:
    """Create the analysis validation node."""

    async def validate_analysis(state: dict) -> dict:
        writer = get_stream_writer()
        plan_results = state.get("plan_results") or []
        answer = state.get("answer") or ""
        synthesis_attempts = state.get("synthesis_attempts", 0)

        warnings: list[str] = []

        # Check step success ratio
        successful = sum(1 for r in plan_results if not r.get("error"))
        total = len(plan_results)
        if total > 0 and successful / total < 0.5:
            warnings.append(
                f"Only {successful}/{total} analysis steps succeeded"
            )

        # Check answer length relative to successful steps
        if successful > 0 and len(answer) < successful * 50:
            warnings.append(
                "Answer seems too brief for the number of successful analysis steps"
            )

        # Check question term coverage
        question = extract_user_question(state["messages"])
        if question:
            key_terms = {
                w.lower()
                for w in question.split()
                if len(w) > 3
            }
            answer_lower = answer.lower()
            covered = sum(1 for t in key_terms if t in answer_lower)
            if key_terms and covered / len(key_terms) < 0.3:
                warnings.append(
                    "Answer may not address key terms from the question"
                )

        if warnings and synthesis_attempts < max_synthesis_attempts:
            guidance = (
                "Please revise the analysis. Issues found: "
                + "; ".join(warnings)
            )
            logger.info(
                "analysis_validation_needs_revision",
                warnings=warnings,
                attempt=synthesis_attempts,
            )
            writer({
                "event": "analysis_validation_warning",
                "warnings": warnings,
            })
            return {"messages": [HumanMessage(content=guidance)]}

        if warnings:
            logger.info(
                "analysis_validation_passed_with_warnings",
                warnings=warnings,
            )
            writer({
                "event": "analysis_validation_warning",
                "warnings": warnings,
            })
        else:
            logger.info("analysis_validation_passed")
            writer({"event": "analysis_validation_passed"})

        return {}

    return validate_analysis
