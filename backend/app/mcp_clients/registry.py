"""Every MCP server the backend talks to, declared in one place.

Each server runs in its own container and is reached over streamable HTTP
at the address set in .env. Three settings decide what the AI may do:

- offer_to_agent: the server's tools are offered to the AI Agent, which may
  call them on its own. Only read-only servers are offered.
- allowed_tools: the only tools the backend will ever call on that server.
  Anything else is refused before a request is sent.
- backend_only: tools of an offered server that only the backend calls,
  so they are never described to the agent or run at its request.

Servers that act on the outside world (publishing, email and calendar)
are never offered to the agent. The backend calls their allowed
tools only after the interviewer has approved the action.
"""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class McpServer:
    url: str
    allowed_tools: frozenset[str]
    offer_to_agent: bool = False
    backend_only: frozenset[str] = frozenset()


def mcp_servers() -> dict[str, McpServer]:
    """The registry, keyed by server name."""
    settings = get_settings()
    return {
        # Knowledge Base search (read-only): for the AI Agent, and for the
        # backend when it checks interview answers against references.
        "rag": McpServer(
            url=settings.mcp_rag_url,
            allowed_tools=frozenset(
                {"search_jd_references", "search_question_bank", "verify_answer"}
            ),
            offer_to_agent=True,
            backend_only=frozenset({"verify_answer"}),
        ),
        # Publishing approved job posts. Called only by the backend.
        "blogger": McpServer(
            url=settings.mcp_blogger_url,
            allowed_tools=frozenset({"create_post"}),
        ),
        # Interview emails and calendar invitations. Called only by the
        # backend, after the interviewer has approved the schedule.
        "google": McpServer(
            url=settings.mcp_google_url,
            allowed_tools=frozenset(
                {
                    "send_email",
                    "create_calendar_event",
                    "update_calendar_event",
                    "cancel_calendar_event",
                }
            ),
        ),
    }
