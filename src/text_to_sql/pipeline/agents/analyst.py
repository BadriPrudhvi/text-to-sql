"""Analysis synthesizer agent — combines step results into comprehensive insights."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer

from text_to_sql.pipeline.agents import extract_user_question
from text_to_sql.pipeline.agents.prompts import ANALYST_PROMPT

logger = structlog.get_logger()


def create_synthesize_analysis_node(
    chat_model: BaseChatModel,
    invoke_with_retry: Callable,
) -> Callable[..., Any]:
    """Create the analysis synthesis node."""

    async def synthesize_analysis(state: dict) -> dict:
        writer = get_stream_writer()
        writer({"event": "analysis_synthesis_started"})

        question = extract_user_question(state["messages"])
        plan_results = state.get("plan_results") or []

        # Build results context
        parts = []
        for i, r in enumerate(plan_results):
            status = "SUCCESS" if not r.get("error") else "FAILED"
            result_data = ""
            if r.get("result"):
                result_data = json.dumps(r["result"][:20], default=str)
            elif r.get("error"):
                result_data = f"Error: {r['error']}"
            parts.append(
                f"### Step {i + 1}: {r['description']}\n"
                f"Status: {status}\n"
                f"SQL: {r.get('sql', 'N/A')}\n"
                f"Data:\n{result_data}"
            )
        results_context = "\n\n".join(parts)

        prompt = ANALYST_PROMPT.format(
            question=question,
            results_context=results_context,
        )
        response = await invoke_with_retry(
            chat_model, [HumanMessage(content=prompt)]
        )
        answer = str(response.content)

        logger.info("analysis_synthesized", answer_length=len(answer))
        writer({"event": "analysis_complete", "answer": answer})

        return {
            "answer": answer,
            "messages": [AIMessage(content=answer)],
            "synthesis_attempts": state.get("synthesis_attempts", 0) + 1,
        }

    return synthesize_analysis
