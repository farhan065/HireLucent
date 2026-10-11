"""Check the Blogger MCP server: list its tools and read the blog's details.

Nothing is published. Usage (inside the backend container):
    python -m scripts.blogger_check
"""

import asyncio
import json
import sys

from mcp import Client

from app.core.config import get_settings


async def check() -> None:
    settings = get_settings()
    if not settings.blogger_blog_id:
        sys.exit("BLOGGER_BLOG_ID is not set in .env.")

    async with Client(settings.mcp_blogger_url) as client:
        tools = await client.list_tools()
        print("Tools:", [tool.name for tool in tools.tools])

        result = await client.call_tool(
            "get_blog_info", {"blogUrl": settings.blogger_blog_id}
        )
        blog = json.loads(result.content[0].text)
        print(f"Blog: {blog['name']} ({blog['url']})")


if __name__ == "__main__":
    asyncio.run(check())
