"""Check the RAG MCP server: list its tools and run one search.

Usage (inside the backend container):
    python -m scripts.mcp_check "backend engineer python fastapi"
"""

import asyncio
import sys

from mcp import Client

from app.core.config import get_settings


async def check(query: str) -> None:
    async with Client(get_settings().mcp_rag_url) as client:
        tools = await client.list_tools()
        print("Tools:", [tool.name for tool in tools.tools])

        result = await client.call_tool("search_jd_references", {"query": query})
        references = result.structured_content["result"]
        print(f"References found: {len(references)}")
        for reference in references:
            print(f"- {reference['source']} (similarity {reference['similarity']})")


if __name__ == "__main__":
    asyncio.run(check(sys.argv[1] if len(sys.argv) > 1 else "backend engineer"))
