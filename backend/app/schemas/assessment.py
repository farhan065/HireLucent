"""Schemas for the post-interview assessment."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Criterion(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class Criteria(BaseModel):
    relevance: Criterion
    accuracy: Criterion | None = Field(default=None, description="Technical questions only.")
    completeness: Criterion
    articulation: Criterion


class Evidence(BaseModel):
    """The part of the answer the evaluation relies on."""

    turn_id: int
    start_ms: int = Field(description="Milliseconds from the start of the interview.")
    quote: str = Field(description="Copied from the turn and checked against it.")


class AccuracySource(BaseModel):
    type: Literal["ai_judgement"] = Field(description="ai_judgement: the AI's own knowledge.")


class AnswerEvaluation(BaseModel):
    answered: Literal["answered", "partly_answered", "not_answered"]
    criteria: Criteria | None = Field(default=None, description="Empty when nothing was said.")
    score: float = Field(
        description="Average of the criteria that apply, or 0 when not answered."
    )
    justification: str
    evidence: Evidence | None = None
    accuracy_source: AccuracySource | None = None


class QAPair(BaseModel):
    """One question and the answer that followed, pointing to the transcript."""

    id: str = Field(description="Q1, Q2, … in the order asked.")
    question: str = Field(description="The question in a short, clear form.")
    question_turn_ids: list[int] = Field(description="Transcript turns that ask it.")
    answer_turn_ids: list[int] = Field(
        description="Transcript turns that answer it. Empty when it was not answered."
    )
    start_ms: int = Field(description="Milliseconds from the start of the interview.")
    end_ms: int
    kind: Literal["technical", "behavioural", "small_talk"] = Field(
        description="Small talk stays in the transcript but is not evaluated."
    )
    follow_up_of: str | None = Field(
        default=None, description="The pair this question follows up or clarifies."
    )
    evaluation: AnswerEvaluation | None = Field(
        default=None, description="Empty for small talk, which is not evaluated."
    )


class AssessmentOut(BaseModel):
    """An interview's assessment as far as it has been made."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    candidate_id: int
    status: Literal["analysed", "draft", "approved"]
    qa_evaluations: list[QAPair]
    created_at: datetime
    updated_at: datetime
