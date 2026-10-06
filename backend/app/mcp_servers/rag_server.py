"""The RAG MCP server: search tools the Recruiter Agent can call.

MCP (Model Context Protocol) is a standard way to offer tools to an AI
agent. This server runs in its own container and speaks MCP over HTTP.
Each tool searches one fixed collection, so the model cannot choose where
to look.

Run with:  python -m app.mcp_servers.rag_server
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.rag import store

logger = get_logger(__name__)
settings = get_settings()

MAX_RESULTS = 2

server = MCPServer("HireLucent RAG")


def find_jd_references(query: str) -> list[dict]:
    """Search the uploaded job description templates for close matches."""
    matches = store.search(store.JD_REFERENCES, query, limit=MAX_RESULTS)
    references = [
        {
            "source": match["metadata"]["source"],
            "similarity": round(1 - match["distance"], 2),
            "text": match["text"],
        }
        for match in matches
        if match["distance"] <= settings.jd_reference_max_distance
    ]
    log_event(
        logger, "jd_references_searched", found=len(matches), used=len(references)
    )
    return references


@server.tool()
def search_jd_references(query: str) -> list[dict]:
    """Find existing job description templates similar to a role.

    Use this before writing a job description, with the role and its main
    skills as the query, for example "backend engineer python fastapi".
    Returns up to two templates to use as references for structure and
    style. An empty list means there is no close match, and the description
    should be written from scratch.
    """
    return find_jd_references(query)


if __name__ == "__main__":
    configure_logging(settings)
    server.run(
        "streamable-http",
        host="0.0.0.0",
        port=settings.mcp_rag_port,
        # The server is reachable only from other containers on the private
        # Docker network, which call it by its service name ("mcp-rag").
        # The host check is meant for servers on a developer's own machine.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
