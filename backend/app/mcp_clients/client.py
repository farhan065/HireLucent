"""One client for every MCP server in the registry.

A connection is opened for each request and closed afterwards, which is
simple and enough for the number of calls the application makes.
"""

import asyncio
import logging
from typing import Any

from mcp import Client
from mcp.types import CallToolResult

from app.core.logging import get_logger, log_event
from app.mcp_clients.registry import McpServer, mcp_servers

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60

# The agent's tool descriptions per server, kept after a successful fetch
# only, so a server that was down is asked again next time.
_agent_tools: dict[str, list[dict[str, Any]]] = {}


class ToolNotAllowedError(Exception):
    """A tool that is not on its server's allow-list was asked for."""


def _server(name: str) -> McpServer:
    server = mcp_servers().get(name)
    if server is None:
        raise ToolNotAllowedError(f"Unknown MCP server: {name}")
    return server


async def call_tool_async(server_name: str, tool: str, arguments: dict) -> CallToolResult:
    """Call one allowed tool on one server."""
    server = _server(server_name)
    if tool not in server.allowed_tools:
        raise ToolNotAllowedError(f"{tool} is not allowed on {server_name}")
    async with Client(server.url) as client:
        return await client.call_tool(tool, arguments)


def call_tool(
    server_name: str,
    tool: str,
    arguments: dict,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CallToolResult:
    """Call one allowed tool and wait for the answer, up to the timeout."""
    return asyncio.run(
        asyncio.wait_for(call_tool_async(server_name, tool, arguments), timeout)
    )


async def _list_tools(server_name: str) -> list[dict[str, Any]]:
    """The server's tools the agent may use, described the way chat models
    expect."""
    server = _server(server_name)
    async with Client(server.url) as client:
        listed = await client.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in listed.tools
        if tool.name in server.allowed_tools and tool.name not in server.backend_only
    ]


def agent_tool_definitions() -> list[dict[str, Any]]:
    """The tools offered to the AI Agent, from every server marked
    offer_to_agent. A server that cannot be reached is left out, so the
    agent keeps working without it."""
    tools: list[dict[str, Any]] = []
    for name, server in mcp_servers().items():
        if not server.offer_to_agent:
            continue
        if name not in _agent_tools:
            try:
                _agent_tools[name] = asyncio.run(_list_tools(name))
            except Exception as exc:
                log_event(
                    logger,
                    "mcp_unavailable",
                    level=logging.WARNING,
                    server=name,
                    error_type=type(exc).__name__,
                )
                continue
        tools.extend(_agent_tools[name])
    return tools


def call_agent_tool(tool: str, arguments: dict) -> Any:
    """Run a tool the AI Agent asked for and return its result.

    Only tools of servers offered to the agent can run this way; anything
    else is refused.
    """
    for name, server in mcp_servers().items():
        if (
            server.offer_to_agent
            and tool in server.allowed_tools
            and tool not in server.backend_only
        ):
            result = call_tool(name, tool, arguments)
            if result.is_error:
                raise RuntimeError(f"MCP tool {tool} reported an error")
            return (result.structured_content or {}).get("result")
    raise ToolNotAllowedError(f"{tool} is not offered to the agent")
