"""Multi-agent analytical query support.

Provides specialized agent nodes for classifying, planning, executing,
and synthesizing complex analytical queries.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage


def extract_user_question(messages: list) -> str:
    """Extract the most recent user question from message history."""
    for msg in reversed(messages):
        if hasattr(msg, "content") and not isinstance(
            msg, (AIMessage, SystemMessage, ToolMessage)
        ):
            return str(msg.content)
    return ""
