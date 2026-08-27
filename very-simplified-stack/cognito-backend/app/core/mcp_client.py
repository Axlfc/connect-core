import asyncio
import logging
from typing import Any, Dict, List, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)

class MCPClientError(Exception):
    """Base exception for MCP Client errors."""
    pass

class MCPClientConnectionError(MCPClientError):
    """Raised when connecting to an MCP server fails."""
    pass

class MCPClientTimeoutError(MCPClientError):
    """Raised when an MCP server operation times out."""
    pass

class MCPClientProtocolError(MCPClientError):
    """Raised when an MCP protocol negotiation or request fails."""
    pass

class MCPServerClient:
    """
    Real Model Context Protocol (MCP) Client.
    Supports stdio and SSE transports for external MCP servers.
    Negotiates capabilities, discovers tools, and invokes remote MCP tools.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        transport_type: str = "auto",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.endpoint_url = endpoint_url
        self.command = command
        self.args = args or []
        self.env = env
        self.timeout = timeout

        if transport_type == "auto":
            if command:
                self.transport_type = "stdio"
            elif endpoint_url:
                self.transport_type = "sse"
            else:
                self.transport_type = "stdio"
        else:
            self.transport_type = transport_type

        self._session = None
        self._exit_stack = None

    async def _create_connection(self):
        """
        Helper context manager or initialization for stdio / sse connection.
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.sse import sse_client
            from contextlib import AsyncExitStack
        except ImportError as e:
            raise MCPClientError(f"Missing required 'mcp' dependency: {e}")

        stack = AsyncExitStack()
        try:
            if self.transport_type == "stdio":
                if not self.command:
                    raise MCPClientConnectionError("stdio transport requires 'command' parameter.")
                server_params = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env=self.env,
                )
                read_stream, write_stream = await stack.enter_async_context(
                    stdio_client(server_params)
                )
            elif self.transport_type == "sse":
                if not self.endpoint_url:
                    raise MCPClientConnectionError("sse transport requires 'endpoint_url' parameter.")
                read_stream, write_stream = await stack.enter_async_context(
                    sse_client(self.endpoint_url)
                )
            else:
                raise MCPClientConnectionError(f"Unsupported transport type: {self.transport_type}")

            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Capability negotiation and handshake
            await asyncio.wait_for(session.initialize(), timeout=self.timeout)
            return stack, session
        except (asyncio.TimeoutError, TimeoutError) as te:
            await stack.aclose()
            raise MCPClientTimeoutError(f"Connection timeout to MCP server after {self.timeout}s: {te}")
        except Exception as e:
            await stack.aclose()
            if isinstance(e, MCPClientError):
                raise
            raise MCPClientConnectionError(f"Failed to connect to MCP server via {self.transport_type}: {e}") from e

    async def connect(self):
        """
        Connects and holds persistent session.
        """
        if self._session is None:
            self._exit_stack, self._session = await self._create_connection()

    async def close(self):
        """
        Closes persistent session.
        """
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error closing MCP client exit stack: {e}")
            finally:
                self._exit_stack = None
                self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def discover_tools(self) -> List[AgentTool]:
        """
        Negotiates capabilities and discovers tools from the remote MCP server.
        """
        logger.info(f"Discovering tools from MCP server (transport={self.transport_type})")

        async def _discover(session):
            tools_response = await asyncio.wait_for(session.list_tools(), timeout=self.timeout)
            mcp_tools = getattr(tools_response, "tools", [])

            wrapped_tools: List[AgentTool] = []
            for t in mcp_tools:
                name = getattr(t, "name", "unnamed_mcp_tool")
                description = getattr(t, "description", "") or "MCP Remote Tool"

                input_schema = getattr(t, "inputSchema", getattr(t, "input_schema", {}))
                if hasattr(input_schema, "model_dump"):
                    input_schema = input_schema.model_dump()
                elif not isinstance(input_schema, dict):
                    input_schema = {"type": "object", "properties": {}}

                wrapped_tools.append(
                    WrappedMCPTool(
                        name=name,
                        description=description,
                        parameters_schema=input_schema,
                        client=self,
                    )
                )
            return wrapped_tools

        try:
            if self._session:
                return await _discover(self._session)
            else:
                async with self:
                    return await _discover(self._session)
        except (asyncio.TimeoutError, TimeoutError) as te:
            logger.error(f"Timeout discovering tools from MCP server: {te}")
            raise MCPClientTimeoutError(f"Timeout discovering tools from MCP server: {te}")
        except Exception as e:
            logger.error(f"Error discovering tools from MCP server: {e}")
            if isinstance(e, MCPClientError):
                raise
            raise MCPClientProtocolError(f"Protocol error during tool discovery: {e}") from e

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Calls a remote tool on the MCP server.
        """
        async def _call(session):
            call_res = await asyncio.wait_for(
                session.call_tool(name, arguments), timeout=self.timeout
            )
            output_parts = []
            content = getattr(call_res, "content", [])
            for c in content:
                if hasattr(c, "text"):
                    output_parts.append(c.text)
                elif hasattr(c, "model_dump_json"):
                    output_parts.append(c.model_dump_json())
                else:
                    output_parts.append(str(c))

            output_str = "\n".join(output_parts) if output_parts else "Tool executed successfully with no content."
            is_error = getattr(call_res, "isError", getattr(call_res, "is_error", False))
            return ToolResult(output=output_str, is_error=is_error)

        try:
            if self._session:
                return await _call(self._session)
            else:
                async with self:
                    return await _call(self._session)
        except (asyncio.TimeoutError, TimeoutError) as te:
            err_msg = f"MCP tool '{name}' timed out after {self.timeout}s: {te}"
            logger.error(err_msg)
            return ToolResult(output=err_msg, is_error=True)
        except Exception as e:
            err_msg = f"MCP tool '{name}' execution error: {e}"
            logger.error(err_msg)
            return ToolResult(output=err_msg, is_error=True)

class WrappedMCPTool(AgentTool):
    """
    AgentTool wrapper for tools discovered dynamically from remote MCP servers.
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        client: MCPServerClient,
        is_read_only: bool = True,
        is_destructive: bool = False,
        concurrency_safe: bool = True,
    ):
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
        self.client = client
        self.is_read_only = is_read_only
        self.is_destructive = is_destructive
        self.concurrency_safe = concurrency_safe

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        return await self.client.call_tool(self.name, arguments)
