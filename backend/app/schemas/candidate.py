"""Schemas for candidates and CV intake."""

from datetime import datetime
from typing import Any

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
    match_counts: dict[str, int] | None = Field(
        default=None,
        description="Requirements met, partially_met and unmet. Empty until matched.",
    )
    requirement_matches: list[dict[str, Any]] | None = Field(
        default=None,
        description="Per requirement: status, evidence quoted from the CV, reason.",
    )
    match_score: float | None = Field(
        default=None, description="How well the CV matches the requirements, 0 to 100."
    )
    rank: int | None = Field(
        default=None, description="Position among the job's matched candidates, 1 is best."
    )
    scores: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Final, criteria and ATS scores, each dimension with its score, weight "
            "and justification, and the ATS parts. Empty until scored."
        ),
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
