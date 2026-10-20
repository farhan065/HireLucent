"""Schemas for the candidate's private interview link."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LinkRequest(BaseModel):
    """The token from the candidate's link. It is sent in the body, never in
    the address, so it does not appear in server logs."""

    token: str = Field(min_length=20, max_length=200)


PIN_PATTERN = r"^\s*\d{4}[\s-]?\d{4}\s*$"


class PinRequest(LinkRequest):
    pin: str = Field(pattern=PIN_PATTERN, description="The 8-digit interview PIN.")


class PinResult(BaseModel):
    """ok, wrong (with the tries left) or locked (until a time, in UTC)."""

    result: Literal["ok", "wrong", "locked"]
    tries_left: int | None = None
    locked_until: datetime | None = None


class EnterRequest(LinkRequest):
    consent: Literal[True] = Field(
        description=(
            "The candidate agreed that the interview is turned into a transcript and, "
            "for an interview with a PIN, that one photo is taken to confirm their identity."
        )
    )
    pin: str | None = Field(
        default=None,
        pattern=PIN_PATTERN,
        description="The interview PIN. Needed for interviews scheduled with a PIN.",
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
    pin_required: bool = Field(
        default=False, description="The candidate must type the PIN from the invitation."
    )


class JoinPass(BaseModel):
    """The candidate's pass for this one interview."""

    access_token: str
    token_type: str = "bearer"
    photo_needed: bool = Field(
        default=False, description="Take the identity photo before the waiting room."
    )


class IdentitySkip(BaseModel):
    reason: Literal["no_camera", "gave_up"]


class IdentityAnswer(BaseModel):
    """What the candidate is told after the photo: done, try again, or
    skipped (no usable photo after the last try). Never the result of the
    check."""

    state: Literal["done", "retry", "skipped"]
    tries_left: int | None = None


class WaitingStatus(BaseModel):
    state: Literal["waiting", "started", "ended"]
