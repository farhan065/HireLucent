"""Schemas for joining a video room."""

from pydantic import BaseModel


class RoomTokenResponse(BaseModel):
    """A pass for one person to join one interview's video room. The url is
    the video server's address for the browser."""

    url: str
    room: str
    identity: str
    token: str
