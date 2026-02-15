from __future__ import annotations

from fastmcp import FastMCP

from text_to_sql.models.responses import status_message


def create_mcp_server() -> FastMCP:
    """Create the MCP server with text-to-SQL tools."""
    mcp = FastMCP("Text-to-SQL Tools")

    @mcp.tool()
    async def generate_sql(question: str) -> dict:
        """Generate SQL from a natural language question.

        Valid queries are auto-executed and results returned immediately.
        Queries with validation errors pause for human review and correction.

        Args:
            question: The natural language question to convert to SQL.
        """
        orchestrator = mcp.state.orchestrator
        record = await orchestrator.submit_question(question)
        return {
            "query_id": record.id,
            "generated_sql": record.generated_sql,
            "validation_errors": record.validation_errors,
            "approval_status": record.approval_status.value,
            "message": status_message(record.approval_status),
            "result": record.result,
            "answer": record.answer,
            "error": record.error,
            "query_type": record.query_type,
            "analysis_plan": record.analysis_plan,
            "analysis_steps": record.analysis_steps,
        }

    @mcp.tool()
    async def execute_sql(query_id: str) -> dict:
        """Execute a previously approved SQL query. Requires prior human approval.

        Args:
            query_id: The ID of the approved query to execute.
        """
        orchestrator = mcp.state.orchestrator
        record = await orchestrator.execute_approved(query_id)
        return {
            "query_id": record.id,
            "status": record.approval_status.value,
            "result": record.result,
            "answer": record.answer,
            "error": record.error,
        }

    return mcp
