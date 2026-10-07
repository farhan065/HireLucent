"""Schemas for candidates and CV intake."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CandidateSummary(BaseModel):
    """A candidate as shown in a job's list of applications."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    source: str
    status: str
    created_at: datetime


class IntakeStatus(BaseModel):
    waiting: int | None = Field(
        description=(
            "Applications that arrived since the last fetch. Empty when the "
            "job is not published or Google could not be asked."
        )
    )
