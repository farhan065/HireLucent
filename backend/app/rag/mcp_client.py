"""The backend's MCP client: finds and calls the tools of the RAG MCP server.

The Recruiter Agent does not contain the search code itself. It asks the
MCP server which tools it offers, gives those to the model, and sends each
tool call to the server.
"""

import asyncio
import logging
from typing import Any

from mcp import Client

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# Tool descriptions are fetched once and reused. They are only kept after a
# successful fetch, so a server that was down is asked again next time.
_tool_definitions: list[dict[str, Any]] | None = None


async def _list_tools() -> list[dict[str, Any]]:
    async with Client(get_settings().mcp_rag_url) as client:
        listed = await client.list_tools()
    # The format chat models expect when they are told about a tool.
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
    ]


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    async with Client(get_settings().mcp_rag_url) as client:
        result = await client.call_tool(name, arguments)
    if result.is_error:
        raise RuntimeError(f"MCP tool {name} reported an error")
    return (result.structured_content or {}).get("result")


def tool_definitions() -> list[dict[str, Any]]:
    """The MCP server's tools, described for the chat model.

    Returns an empty list if the server cannot be reached, so the assistant
    keeps working without search.
    """
    global _tool_definitions
    if _tool_definitions is None:
        try:
            _tool_definitions = asyncio.run(_list_tools())
        except Exception as exc:
            log_event(
                logger,
                "mcp_unavailable",
                level=logging.WARNING,
                error_type=type(exc).__name__,
            )
            return []
    return _tool_definitions


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Run one tool on the MCP server and return its result."""
    return asyncio.run(_call_tool(name, arguments))
