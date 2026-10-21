"""Schemas for decisions and feedback emails (innovation feature F11)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.task import TaskResponse

MAX_BODY_CHARS = 3_000


class DecisionChange(BaseModel):
    """Hire or reject after the interview, or no decision."""

    decision: Literal["hire", "reject"] | None


class DecisionRule(BaseModel):
    """Hire by one rule, the rest of the ranked candidates are rejected:
    the top N, or everyone with at least a given overall score."""

    top: int | None = Field(default=None, ge=1, le=500)
    min_score: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def exactly_one_rule(self) -> "DecisionRule":
        if (self.top is None) == (self.min_score is None):
            raise ValueError("Give either top or min_score.")
        return self


class DecisionResult(BaseModel):
    hired: int
    rejected: int
    skipped: int = Field(description="Candidates whose email is already sent keep their decision.")


class CandidateDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision: str | None
    decided_at: datetime | None
    feedback_status: str | None


class ComposeRequest(BaseModel):
    candidate_ids: list[int] = Field(min_length=1, max_length=200)


class SendAllRequest(BaseModel):
    stage: Literal["screening", "interview"]


class FeedbackWarning(BaseModel):
    code: str = Field(description="Which rule, for example score or tone.")
    message: str = Field(description="What was found, naming the words.")
    quote: str = Field(default="", description="The sentence it was found in.")
    words: list[str] = Field(default_factory=list, description="The exact words, to highlight.")


class EvidencePoint(BaseModel):
    group: Literal["strength", "growth", "level"]
    id: str = Field(description="A requirement id (R4), a report point (S1, W2) or a level.")
    text: str
    note: str


class FeedbackOut(BaseModel):
    """A candidate's feedback email, as the interviewer sees it."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: int
    kind: Literal["screening_reject", "interview_reject", "hire", "cv_unreadable"]
    status: Literal["waiting_review", "sending", "sent", "failed", "discarded"]
    written_by: Literal["ai", "template"]
    subject: str
    body: str
    evidence: list[EvidencePoint] = Field(
        description="What each point is based on. Shown to the interviewer only."
    )
    warnings: list[FeedbackWarning]
    error_message: str | None
    sent_anyway: bool
    approved_by_name: str | None
    approved_at: datetime | None
    sent_at: datetime | None
    updated_at: datetime


class FeedbackReview(BaseModel):
    """The interviewer's review of a draft email."""

    action: Literal["approve", "send_anyway", "edit", "request_changes", "discard"]
    note: str | None = Field(
        default=None, min_length=1, max_length=1000, description="request_changes: what to change."
    )
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(
        default=None, min_length=1, max_length=MAX_BODY_CHARS, description="edit: the new text."
    )

    @model_validator(mode="after")
    def check_action(self) -> "FeedbackReview":
        if self.action == "request_changes" and not (self.note or "").strip():
            raise ValueError("Write what should change.")
        if self.action == "edit" and not (self.body or "").strip():
            raise ValueError("The email cannot be empty.")
        return self


class FeedbackActivity(BaseModel):
    """A job's feedback emails: the writing or sending running now, the last
    finished one, and how many emails are still to send per stage. While a
    task runs, its result holds candidate_ids, current and failures."""

    running: TaskResponse | None
    last: TaskResponse | None
    screening_to_send: int = Field(description="Candidates not shortlisted, email not sent.")
    interview_to_send: int = Field(description="Decided after the interview, email not sent.")
