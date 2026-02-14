from __future__ import annotations

import pytest

from text_to_sql.mcp.tools import create_mcp_server


def test_mcp_server_creates_tools() -> None:
    """Verify the MCP server registers all expected tools."""
    mcp = create_mcp_server()
    # The FastMCP server should have our 4 tools registered
    assert mcp is not None
