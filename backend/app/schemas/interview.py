"""Schemas for interview sessions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InterviewSessionSummary(BaseModel):
    """An interview as shown in a job's list of interviews. The join token
    and its hash are never included."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    candidate_name: str
    scheduled_start: datetime = Field(description="Start time, in UTC.")
    scheduled_end: datetime = Field(description="End time, in UTC.")
    status: str = Field(description="scheduled, in_progress, completed or cancelled.")
    candidate_joined_at: datetime | None = None
    interviewer_joined_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    cancelled_at: datetime | None = None
