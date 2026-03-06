"""Multi-agent analytical query support.

Provides specialized agent nodes for classifying, planning, executing,
and synthesizing complex analytical queries.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage


def extract_text(content: str | list) -> str:
    """Extract plain text from LLM response content.

    Gemini models return content as a list of blocks
    (e.g. [{'type': 'text', 'text': '...'}]) while Anthropic/OpenAI
    return a plain string. This normalizes both formats.
    """
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def extract_user_question(messages: list) -> str:
    """Extract the most recent user question from message history."""
    for msg in reversed(messages):
        if hasattr(msg, "content") and not isinstance(
            msg, (AIMessage, SystemMessage, ToolMessage)
        ):
            return extract_text(msg.content)
    return ""
