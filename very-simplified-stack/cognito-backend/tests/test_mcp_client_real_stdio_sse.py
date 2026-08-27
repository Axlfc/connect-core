import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.mcp_client import (
    MCPServerClient,
    WrappedMCPTool,
    MCPClientError,
    MCPClientConnectionError,
    MCPClientTimeoutError,
    MCPClientProtocolError,
)
from app.core.tools.base import ToolContext

pytestmark = pytest.mark.asyncio

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

async def test_real_stdio_mcp_client_discovery_and_tool_call():
    """
    Integration test connecting via stdio transport to real reference MCP server (FastMCP app.services.mcp_server).
    Verifies discovery and execution of real external tools over stdio protocol.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = BACKEND_DIR
    env["COGNITO_MCP_INSECURE_DEV"] = "true"

    client = MCPServerClient(
        transport_type="stdio",
        command=sys.executable,
        args=["-m", "app.services.mcp_server"],
        env=env,
        timeout=10.0,
    )

    async with client:
        tools = await client.discover_tools()
        assert len(tools) > 0

        tool_names = [t.name for t in tools]
        assert "cognito_architecture_context" in tool_names

        arch_tool = next(t for t in tools if t.name == "cognito_architecture_context")
        assert isinstance(arch_tool, WrappedMCPTool)

        ctx = ToolContext(cwd=".", trusted=True, protected_files=set())
        res = await arch_tool.execute({}, ctx)

        assert res.is_error is False
        assert "Cognito-Codex Router Stack" in res.output

async def test_mcp_client_invalid_command_connection_error():
    """
    Unit/Integration test: connecting with an invalid binary raises MCPClientConnectionError.
    """
    client = MCPServerClient(
        transport_type="stdio",
        command="non_existent_binary_xyz123",
        args=[],
        timeout=2.0,
    )

    with pytest.raises(MCPClientConnectionError) as exc_info:
        async with client:
            pass

    assert "Failed to connect to MCP server via stdio" in str(exc_info.value) or "No such file" in str(exc_info.value)

async def test_mcp_client_connection_timeout_error():
    """
    Unit test: connection timeout raises MCPClientTimeoutError.
    """
    client = MCPServerClient(
        transport_type="stdio",
        command=sys.executable,
        args=["-c", "import time; time.sleep(10)"],
        timeout=0.2,
    )

    with pytest.raises(MCPClientTimeoutError) as exc_info:
        async with client:
            pass

    assert "Connection timeout" in str(exc_info.value)

async def test_mcp_client_sse_transport_mocked():
    """
    Unit test verifying SSE transport initialization and tool discovery via mocked _create_connection.
    """
    mock_tool = MagicMock()
    mock_tool.name = "sse_remote_tool"
    mock_tool.description = "Tool discovered via SSE"
    mock_tool.input_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}

    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_tool]))

    mock_call_res = MagicMock()
    mock_call_res.content = [MagicMock(text="SSE tool output result")]
    mock_call_res.isError = False
    mock_session.call_tool = AsyncMock(return_value=mock_call_res)

    mock_stack = AsyncMock()

    client = MCPServerClient(
        endpoint_url="http://localhost:8000/sse",
        transport_type="sse",
        timeout=5.0,
    )

    with patch.object(client, "_create_connection", return_value=(mock_stack, mock_session)):
        async with client:
            tools = await client.discover_tools()
            assert len(tools) == 1
            assert tools[0].name == "sse_remote_tool"

            ctx = ToolContext(cwd=".", trusted=True, protected_files=set())
            res = await tools[0].execute({"msg": "hello"}, ctx)
            assert res.is_error is False
            assert "SSE tool output result" in res.output
