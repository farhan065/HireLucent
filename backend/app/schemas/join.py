"""Schemas for the candidate's private interview link."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LinkRequest(BaseModel):
    """The token from the candidate's link. It is sent in the body, never in
    the address, so it does not appear in server logs."""

    token: str = Field(min_length=20, max_length=200)


class EnterRequest(LinkRequest):
    consent: Literal[True] = Field(
        description="The candidate agreed that the interview is turned into a transcript."
    )


class LinkInfo(BaseModel):
    """What the candidate's page shows. Times are in UTC; the page shows
    them in the candidate's own time zone."""

    state: Literal["too_early", "open", "ended"]
    first_name: str
    job_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    opens_at: datetime = Field(description="When Join opens.")
    length_minutes: int


class JoinPass(BaseModel):
    """The candidate's pass for this one interview."""

    access_token: str
    token_type: str = "bearer"


class WaitingStatus(BaseModel):
    state: Literal["waiting", "started", "ended"]
