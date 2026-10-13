"""Rooms on the LiveKit video server.

A token lets one browser join one room. It is signed with the LiveKit key
and secret, sent to the browser and never stored. When an interview ends,
its room is closed on the server, which disconnects everyone in it.
"""

import asyncio
import logging
from datetime import timedelta

from livekit import api

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

NOT_CONFIGURED = (
    "Video is not set up. Add the LiveKit key and secret to the .env file "
    "and restart the application."
)


def room_name(session_id: int) -> str:
    """One room per interview."""
    return f"interview-{session_id}"


def create_room_token(
    room: str,
    identity: str,
    name: str,
    valid_for: timedelta,
    *,
    hidden: bool = False,
    can_publish: bool = True,
) -> str:
    """A token that lets one participant join one room, send their camera,
    microphone and screen, and receive the other participant's.

    The transcription worker joins hidden and without publishing: the two
    people in the interview never see it, and it only listens."""
    settings = get_settings()
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise ServiceUnavailableError(NOT_CONFIGURED)
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=can_publish,
        can_publish_data=can_publish,
        can_subscribe=True,
        hidden=hidden,
    )
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_ttl(valid_for)
        .to_jwt()
    )


async def _delete_room(room: str) -> None:
    settings = get_settings()
    client = api.LiveKitAPI(
        url=settings.livekit_api_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    try:
        await client.room.delete_room(api.DeleteRoomRequest(room=room))
    finally:
        await client.aclose()


def close_room(room: str) -> bool:
    """Close a room, disconnecting everyone in it. Returns False if the video
    server could not be reached; the browsers then leave on their own when
    they see the interview has ended."""
    try:
        asyncio.run(_delete_room(room))
    except Exception as exc:
        log_event(
            logger, "video_room_close_failed", level=logging.WARNING, error_type=type(exc).__name__
        )
        return False
    return True
