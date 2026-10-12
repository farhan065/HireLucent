"""Schemas for interview sessions."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


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


class InterviewTime(BaseModel):
    """A start and end time, each with its time zone."""

    start: AwareDatetime
    end: AwareDatetime


class ScheduleSlot(InterviewTime):
    candidate_id: int


class ScheduleRequest(BaseModel):
    """Interviews to schedule for a job, at most 20 at once."""

    interviews: list[ScheduleSlot] = Field(min_length=1, max_length=20)

    @field_validator("interviews")
    @classmethod
    def one_interview_per_candidate(cls, interviews: list[ScheduleSlot]) -> list[ScheduleSlot]:
        ids = [slot.candidate_id for slot in interviews]
        if len(ids) != len(set(ids)):
            raise ValueError("Each candidate can be scheduled only once at a time.")
        return interviews


class ScheduleOutcome(BaseModel):
    """What happened when one candidate was scheduled."""

    candidate_id: int
    candidate_name: str
    status: Literal["scheduled", "failed"]
    session_id: int | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    warning: str | None = Field(
        default=None, description="Scheduled, but something could not be sent."
    )
    error: str | None = Field(default=None, description="Why it was not scheduled.")


class InterviewChange(BaseModel):
    """An interview after it was moved or cancelled."""

    interview: InterviewSessionSummary
    warning: str | None = Field(
        default=None, description="Done, but something could not be sent."
    )
