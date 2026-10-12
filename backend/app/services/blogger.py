"""Publishes a post through the Blogger MCP server.

Only the server's create_post tool is ever called (the registry allows no
other), and only from the publishing tool after the interviewer has
approved the post. The server's tools are never offered to the language
model.
"""

import asyncio
import logging
import re

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.mcp_clients import client

logger = get_logger(__name__)

PUBLISH_TIMEOUT_SECONDS = 60
PUBLISH_FAILED = (
    "The post could not be published. Check that the Blogger service is "
    "running and the Google sign-in has not expired, then try again."
)
_POST_URL = re.compile(r"^URL: (https?://\S+)", re.MULTILINE)


async def _create_post(title: str, html: str) -> str:
    result = await client.call_tool_async(
        "blogger",
        "create_post",
        {"blogId": get_settings().blogger_blog_id, "title": title, "content": html},
    )
    return result.content[0].text


def create_post(title: str, html: str) -> str:
    """Publish a post and return its public address."""
    try:
        reply = asyncio.run(
            asyncio.wait_for(_create_post(title, html), PUBLISH_TIMEOUT_SECONDS)
        )
        match = _POST_URL.search(reply)
    except Exception as exc:
        log_event(
            logger,
            "blogger_publish_failed",
            level=logging.WARNING,
            error_type=type(exc).__name__,
        )
        raise ServiceUnavailableError(PUBLISH_FAILED) from exc
    if match is None:
        log_event(logger, "blogger_reply_without_url", level=logging.WARNING)
        raise ServiceUnavailableError(PUBLISH_FAILED)
    return match.group(1)
