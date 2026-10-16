from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TranscriptTurnOut(BaseModel):
    """One stretch of speech by one person."""

    id: int
    speaker: Literal["interviewer", "candidate"]
    start_ms: int = Field(description="Milliseconds from the start of the interview.")
    end_ms: int
    spoken_at: datetime | None = Field(
        default=None, description="Clock time the turn began, in UTC."
    )
    text: str


class Transcript(BaseModel):
    """An interview's transcript, in the order it was spoken."""

    session_id: int
    started_at: datetime | None
    turns: list[TranscriptTurnOut]
