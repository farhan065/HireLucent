"""Schemas for the post-interview assessment."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.task import TaskResponse


class Criterion(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class Criteria(BaseModel):
    relevance: Criterion
    accuracy: Criterion | None = Field(
        default=None,
        description="Technical questions, and company questions checked against a reference.",
    )
    completeness: Criterion
    articulation: Criterion


class Evidence(BaseModel):
    """The part of the answer the evaluation relies on."""

    turn_id: int
    start_ms: int = Field(description="Milliseconds from the start of the interview.")
    quote: str = Field(description="Copied from the turn and checked against it.")


class AccuracySource(BaseModel):
    """Where a technical or company answer's accuracy judgement comes from."""

    type: Literal["reference", "ai_judgement", "not_checked"] = Field(
        description="reference: checked against a Knowledge Base reference passage. "
        "ai_judgement: a technical answer with no usable reference, judged from the "
        "AI interviewer's own knowledge. not_checked: a company answer with no usable "
        "reference, so its accuracy is not scored."
    )
    source: str | None = Field(default=None, description="The reference document's name.")
    passage: str | None = Field(default=None, description="The passage checked against.")
    similarity: float | None = Field(
        default=None, description="How close the passage is to the answer, 0 to 1."
    )


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
    kind: Literal["technical", "behavioural", "company", "small_talk"] = Field(
        description="Small talk stays in the transcript but is not evaluated."
    )
    follow_up_of: str | None = Field(
        default=None, description="The pair this question follows up or clarifies."
    )
    requirement_ids: list[str] = Field(
        default_factory=list, description="The job requirements the question explores."
    )
    evaluation: AnswerEvaluation | None = Field(
        default=None, description="Empty for small talk, which is not evaluated."
    )


class QuestionScore(BaseModel):
    pair_id: str
    score: float


class CvResult(BaseModel):
    """What CV screening found for the requirement."""

    status: Literal["met", "partially_met", "unmet"]
    evidence: str = ""


class CoverageEntry(BaseModel):
    """How the interview explored one job requirement."""

    requirement_id: str
    text: str
    priority: Literal["must_have", "preferred"]
    status: Literal["covered", "weak", "not_explored"] = Field(
        description="covered: average answer score 60 or more. weak: explored, but "
        "below 60. not_explored: no question touched it."
    )
    average: float | None = Field(description="Average score of the answers that explored it.")
    question_scores: list[QuestionScore]
    mixed: bool = Field(description="Covered, but one of its answers scored below 40.")
    cv: CvResult | None = Field(description="Empty when the CV was not matched to it.")


class QuestionSuggestion(BaseModel):
    """A question from the interview offered for the question bank."""

    pair_id: str
    question: str
    kind: Literal["technical", "behavioural", "company"]
    added: bool


class AddQuestionsRequest(BaseModel):
    pair_ids: list[str] = Field(
        min_length=1, max_length=100, description="The suggestions the interviewer ticked."
    )


class ClaimSource(BaseModel):
    """Where a conclusion comes from: a transcript segment, or what CV
    screening found for a requirement."""

    type: Literal["transcript", "cv"]
    pair_id: str | None = Field(default=None, description="transcript: the question.")
    question: str | None = None
    turn_id: int | None = Field(default=None, description="transcript: the turn.")
    start_ms: int | None = Field(
        default=None, description="transcript: milliseconds from the start of the interview."
    )
    quote: str | None = Field(default=None, description="transcript: the words relied on.")
    requirement_id: str | None = Field(default=None, description="cv: the requirement.")
    requirement: str | None = None
    status: Literal["met", "partially_met", "unmet"] | None = Field(
        default=None, description="cv: the screening result; empty when not screened."
    )
    evidence: str | None = Field(default=None, description="cv: the CV text relied on.")


class Claim(BaseModel):
    """One conclusion of the report, with its sources."""

    id: str = Field(description="S1, W1, G1, V1, … by list.")
    text: str
    sources: list[ClaimSource]


class ReviewRequest(BaseModel):
    """The interviewer's review of a draft report."""

    action: Literal["approve", "request_changes", "edit"]
    note: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
        description="request_changes: what the AI should change.",
    )
    summary: str | None = Field(
        default=None, min_length=1, max_length=1500, description="edit: the new summary."
    )
    remove: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="edit: ids of strengths or weaknesses to remove.",
    )

    @model_validator(mode="after")
    def check_action(self) -> "ReviewRequest":
        if self.action == "request_changes" and not (self.note or "").strip():
            raise ValueError("Write what should change.")
        if self.action == "edit" and not ((self.summary or "").strip() or self.remove):
            raise ValueError("Change the summary or remove at least one point.")
        return self


class AssessmentOut(BaseModel):
    """An interview's assessment as far as it has been made."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    candidate_id: int
    status: Literal["analysed", "draft", "approved"]
    screening_score: float | None = Field(
        default=None, description="The candidate's final score from CV screening."
    )
    qa_evaluations: list[QAPair]
    coverage_map: list[CoverageEntry]
    question_suggestions: list[QuestionSuggestion] | None = Field(
        default=None, description="Empty when the question bank could not be searched."
    )
    # The report, from the draft on. Empty while only the answers are evaluated.
    cv_score: float | None = None
    interview_score: float | None = Field(
        default=None, description="Average score of the evaluated answers."
    )
    overall_score: float | None = Field(
        default=None, description="40% CV score + 60% interview score."
    )
    suitability: Literal["strong_fit", "possible_fit", "not_a_fit"] | None = Field(
        default=None,
        description="From the overall score: strong_fit 70+, possible_fit 60-69, "
        "not_a_fit below 60. Decision support only.",
    )
    report: str | None = Field(default=None, description="The summary.")
    strengths: list[Claim] | None = None
    weaknesses: list[Claim] | None = None
    gaps: list[Claim] | None = Field(
        default=None, description="Requirements the interview never explored."
    )
    areas_to_verify: list[Claim] | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CoverageCounts(BaseModel):
    covered: int
    weak: int
    not_explored: int
    total: int


class RankedAssessment(BaseModel):
    """One completed interview in the job's ranked list. Interviews without
    an overall score are listed too, unranked."""

    session_id: int
    candidate_id: int
    candidate_name: str
    started_at: datetime | None
    ended_at: datetime | None
    scheduled_start: datetime
    rank: int | None = Field(description="1 for the highest overall score; empty if unranked.")
    status: Literal["analysed", "draft", "approved"] | None = Field(
        description="The assessment's status; empty until the interview is evaluated."
    )
    cv_score: float | None
    interview_score: float | None
    overall_score: float | None
    suitability: Literal["strong_fit", "possible_fit", "not_a_fit"] | None
    answers_evaluated: int = Field(description="Answers the interview score averages.")
    coverage: CoverageCounts | None
    strengths: list[Claim] | None
    weaknesses: list[Claim] | None
    gaps: list[Claim] | None
    areas_to_verify: list[Claim] | None
    approved_at: datetime | None


class EvaluationActivity(BaseModel):
    """A job's interview evaluations: the one running, the last finished one
    and how many completed interviews are waiting. While a task runs, its
    result holds session_ids, current and failures (each with session_id
    and reason)."""

    running: TaskResponse | None
    last: TaskResponse | None
    waiting: int = Field(description="Completed interviews not evaluated yet.")
