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
    cv_text_source: str | None = Field(
        description='How the CV was read: "text", "ocr", or empty if not read yet.'
    )
    screening_error: str | None
    excluded_reason: str | None = Field(
        default=None, description="Why screening excluded the candidate, one reason per line."
    )
    must_haves_met: bool | None = Field(
        default=None, description="Whether the must-have check passed. Empty until it has run."
    )
    created_at: datetime


class IntakeStatus(BaseModel):
    waiting: int | None = Field(
        description=(
            "Applications that arrived since the last fetch. Empty when the "
            "job is not published or Google could not be asked."
        )
    )
