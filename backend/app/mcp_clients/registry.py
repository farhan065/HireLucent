"""Every MCP server the backend talks to, declared in one place.

Each server runs in its own container and is reached over streamable HTTP
at the address set in .env. Two settings decide what the AI may do:

- offer_to_agent: the server's tools are offered to the AI Agent, which may
  call them on its own. Only read-only servers are offered.
- allowed_tools: the only tools the backend will ever call on that server.
  Anything else is refused before a request is sent.

Servers that act on the outside world (publishing, later email and
calendar) are never offered to the agent. The backend calls their allowed
tools only after the interviewer has approved the action.
"""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class McpServer:
    url: str
    allowed_tools: frozenset[str]
    offer_to_agent: bool = False


def mcp_servers() -> dict[str, McpServer]:
    """The registry, keyed by server name."""
    settings = get_settings()
    return {
        # Knowledge Base search for the AI Agent (read-only).
        "rag": McpServer(
            url=settings.mcp_rag_url,
            allowed_tools=frozenset({"search_jd_references"}),
            offer_to_agent=True,
        ),
        # Publishing approved job posts. Called only by the backend.
        "blogger": McpServer(
            url=settings.mcp_blogger_url,
            allowed_tools=frozenset({"create_post"}),
        ),
    }
