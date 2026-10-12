"""Schemas for joining a video room."""

from pydantic import BaseModel


class RoomTokenResponse(BaseModel):
    url: str
    room: str
    identity: str
    token: str
