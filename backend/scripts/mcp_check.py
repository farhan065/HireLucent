"""Check the MCP servers in the registry, then run one Knowledge Base search.

For each server it shows the tools the server lists, which of them the
backend is allowed to call, and whether they are offered to the AI Agent.
Nothing is published. Usage (inside the backend container):
    python -m scripts.mcp_check "backend engineer python fastapi"
"""

import asyncio
import sys

from mcp import Client

from app.mcp_clients import client
from app.mcp_clients.registry import mcp_servers


async def list_servers() -> None:
    for name, server in mcp_servers().items():
        try:
            async with Client(server.url) as connection:
                listed = [tool.name for tool in (await connection.list_tools()).tools]
        except Exception as exc:
            print(f"{name}: not reachable ({type(exc).__name__})")
            continue
        allowed = sorted(server.allowed_tools)
        missing = [tool for tool in allowed if tool not in listed]
        print(
            f"{name}: {len(listed)} tools listed · allowed {allowed}"
            f" · offered to the agent: {'yes' if server.offer_to_agent else 'no'}"
        )
        if missing:
            print(f"  allowed but not listed by the server: {missing}")


def search(query: str) -> None:
    references = client.call_agent_tool("search_jd_references", {"query": query})
    print(f"References found: {len(references)}")
    for reference in references:
        print(f"- {reference['source']} (similarity {reference['similarity']})")


if __name__ == "__main__":
    asyncio.run(list_servers())
    search(sys.argv[1] if len(sys.argv) > 1 else "backend engineer")
