"""Schemas for the post-interview assessment."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
