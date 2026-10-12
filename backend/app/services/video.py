"""Room tokens for the LiveKit video server.

A token lets one browser join one room. It is signed with the LiveKit key
and secret, sent to the browser and never stored.
"""

from datetime import timedelta

from livekit import api

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

NOT_CONFIGURED = (
    "Video is not set up. Add the LiveKit key and secret to the .env file "
    "and restart the application."
)


def create_room_token(
    room: str,
    identity: str,
    name: str,
    valid_for: timedelta,
) -> str:
    """A token that lets one participant join one room, send their camera
    and microphone, and receive the other participant's."""
    settings = get_settings()
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise ServiceUnavailableError(NOT_CONFIGURED)
    grants = api.VideoGrants(
        room_join=True, room=room, can_publish=True, can_subscribe=True
    )
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_ttl(valid_for)
        .to_jwt()
    )
