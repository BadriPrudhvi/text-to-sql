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
        return _record_to_dict(record)

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
            "query_type": record.query_type,
            "analysis_plan": record.analysis_plan,
            "analysis_steps": record.analysis_steps,
        }

    @mcp.tool()
    async def create_session() -> dict:
        """Create a new conversation session for multi-turn queries.

        Sessions allow the LLM to remember prior questions and answers,
        enabling follow-up questions like "now filter by age > 30".
        """
        orchestrator = mcp.state.orchestrator
        session_store = orchestrator.session_store
        if session_store is None:
            return {"error": "Session support is not enabled on this server."}
        session = await session_store.create()
        return {"session_id": session.id}

    @mcp.tool()
    async def query_in_session(question: str, session_id: str) -> dict:
        """Ask a question within a conversation session.

        The LLM remembers prior questions in the same session, enabling
        follow-up queries without repeating context.

        Args:
            question: The natural language question to convert to SQL.
            session_id: The session ID from create_session.
        """
        orchestrator = mcp.state.orchestrator
        session_store = orchestrator.session_store
        if session_store is None:
            return {"error": "Session support is not enabled on this server."}
        try:
            await session_store.get(session_id)
        except KeyError:
            return {"error": f"Session {session_id} not found."}
        record = await orchestrator.submit_question_in_session(question, session_id)
        return _record_to_dict(record)

    @mcp.tool()
    async def get_session_history(session_id: str) -> dict:
        """Get all queries in a conversation session.

        Args:
            session_id: The session ID from create_session.
        """
        orchestrator = mcp.state.orchestrator
        session_store = orchestrator.session_store
        if session_store is None:
            return {"error": "Session support is not enabled on this server."}
        try:
            session = await session_store.get(session_id)
        except KeyError:
            return {"error": f"Session {session_id} not found."}

        queries = []
        for qid in session.query_ids:
            try:
                record = await orchestrator.query_store.get(qid)
                queries.append(_record_to_dict(record))
            except KeyError:
                continue

        return {
            "session_id": session.id,
            "queries": queries,
            "total": len(queries),
        }

    def _record_to_dict(record) -> dict:
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

    return mcp
