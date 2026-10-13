"""The AI Agent's MCP tools.

The Recruiter Agent does not contain the search code itself. It is offered
the tools of the MCP servers the registry marks for the agent (today the
RAG server's Knowledge Base search), and each tool call is sent to its
server. Servers that act on the outside world are never offered.
"""

from typing import Any

from app.mcp_clients import client


def tool_definitions() -> list[dict[str, Any]]:
    """The tools offered to the agent, described for the chat model.

    Returns an empty list if no server can be reached, so the assistant
    keeps working without search.
    """
    return client.agent_tool_definitions()


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Run one tool the agent asked for and return its result."""
    return client.call_agent_tool(name, arguments)
