"""Schemas for the post-interview assessment."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.task import TaskResponse

# An id such as Q3 or S1, sent back by the screens.
ItemId = Annotated[str, Field(min_length=1, max_length=20)]


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


class ShownCriterion(BaseModel):
    """Problem-solving or depth of experience in one answer (F9), with the
    candidate's words that show it."""

    score: int = Field(ge=0, le=100)
    reason: str
    evidence: Evidence


class AnswerEvaluation(BaseModel):
    answered: Literal["answered", "partly_answered", "not_answered"]
    criteria: Criteria | None = Field(default=None, description="Empty when nothing was said.")
    score: float = Field(
        description="Average of the criteria that apply, or 0 when not answered."
    )
    justification: str
    evidence: Evidence | None = None
    accuracy_source: AccuracySource | None = None
    problem_solving: ShownCriterion | None = Field(
        default=None,
        description="Only when the answer shows problem-solving (F9). Feeds the interview "
        "performance dimension, never this answer's score.",
    )
    depth: ShownCriterion | None = Field(
        default=None,
        description="Only when the answer describes the candidate's own work (F9). Feeds "
        "the interview performance dimension, never this answer's score.",
    )


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
    pair_ids: list[ItemId] = Field(
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
    remove: list[ItemId] = Field(
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


class ClaimReview(BaseModel):
    """How the interviewer handled a contradiction or unverified claim."""

    status: Literal["checked", "dismissed"]
    note: str | None = None
    by_id: int | None = Field(default=None, description="The interviewer who marked it.")
    by_name: str | None = None
    at: datetime


ClaimResult = Literal["consistent", "contradiction", "unverified", "not_discussed", "not_checked"]


class CvClaim(BaseModel):
    """One claim from the CV, compared with the interview (F8). A prompt for
    the interviewer to check before deciding, never a finding about the
    candidate."""

    id: str = Field(description="C1, C2, … in the CV's order.")
    section: Literal[
        "total_experience", "work_experience", "project", "certification", "education", "skill"
    ]
    title: str
    cv_text: str = Field(description="The claim as the CV words it.")
    detail: str = Field(default="", description="Where in the CV, for example the job and dates.")
    result: ClaimResult = Field(
        description="consistent: the interview supports it. contradiction: something said "
        "clearly conflicts with it. unverified: it came up, but nothing backs it up. "
        "not_discussed: it never came up. not_checked: no result could be proven."
    )
    question_id: str | None = Field(default=None, description="The question relied on.")
    question: str | None = None
    turn_id: int | None = None
    start_ms: int | None = Field(
        default=None, description="Milliseconds from the start of the interview."
    )
    quote: str | None = Field(default=None, description="The candidate's words, checked.")
    reason: str | None = Field(default=None, description="A short, neutral reason.")
    review: ClaimReview | None = Field(
        default=None, description="contradiction and unverified: checked or dismissed."
    )


class ClaimChecks(BaseModel):
    """The interview's CV claim check (F8)."""

    status: Literal["checked", "not_checked"] = Field(
        description="not_checked: the AI was not available; check the claims again."
    )
    checked_at: datetime
    claims: list[CvClaim]


class ClaimReviewRequest(BaseModel):
    """The interviewer marks a contradiction or unverified claim."""

    action: Literal["checked", "dismissed", "reopen"]
    note: str | None = Field(default=None, max_length=500, description="Optional.")


class DimensionAnswer(BaseModel):
    """One answer an interview performance dimension rests on."""

    pair_id: str
    question: str
    kind: Literal["technical", "behavioural", "company"]
    score: float
    reason: str | None = None
    quote: str | None = Field(default=None, description="The transcript's own words.")
    turn_id: int | None = None
    start_ms: int


class DimensionRequirement(BaseModel):
    """One explored requirement the alignment dimension rests on."""

    requirement_id: str
    text: str
    priority: Literal["must_have", "preferred"]
    status: Literal["covered", "weak", "not_explored"]
    average: float | None


class InterviewDimension(BaseModel):
    key: Literal[
        "technical", "communication", "relevance", "problem_solving", "depth", "alignment"
    ]
    name: str
    score: float | None = Field(description="0 to 100; empty when not assessed.")
    based_on: str = Field(description="What the dimension rests on, in words.")
    answers: list[DimensionAnswer] = Field(default_factory=list)
    requirements: list[DimensionRequirement] = Field(
        default_factory=list, description="Alignment only."
    )
    not_explored: list[str] = Field(default_factory=list, description="Alignment only.")


class InterviewDimensions(BaseModel):
    """The interview performance score (F9) and its six dimensions."""

    status: Literal["scored", "not_enough"] = Field(
        description="not_enough: fewer than min_assessed dimensions could be assessed, "
        "so there is no interview score."
    )
    score: float | None = Field(description="Average of the assessed dimensions.")
    assessed: int
    total: int
    min_assessed: int
    dimensions: list[InterviewDimension]


class QualityRef(BaseModel):
    """What a finding or recommendation rests on, shown as a chip."""

    type: Literal["question", "requirement", "measure", "time"]
    id: str | None = Field(default=None, description="Q… or R…, for a question or requirement.")
    start_ms: int | None = Field(default=None, description="From the interview start.")
    label: str


class QualityFinding(BaseModel):
    id: str = Field(description="F1, F2, …")
    kind: str
    text: str = Field(description="The fact, written by code.")
    refs: list[QualityRef]


class QualityRecommendation(BaseModel):
    id: str = Field(description="M1, M2, …")
    text: str = Field(
        description="Written by the AI from the findings; every id and number checked."
    )
    example_question: str | None = None
    finding_ids: list[str]
    kinds: list[str]
    refs: list[QualityRef]


class QualityRecommendations(BaseModel):
    status: Literal["written", "none_needed", "not_written"] = Field(
        description="not_written: the AI was not available, or none could be proven."
    )
    reason: str | None = None
    items: list[QualityRecommendation]


class LittleSignal(BaseModel):
    id: str
    reason: str


class QuestionRef(BaseModel):
    id: str


class QuestionsPart(BaseModel):
    score: float
    useful: int
    total: int = Field(description="Job-related questions; small talk is left out.")
    little_signal: list[LittleSignal]
    not_linked: list[QuestionRef]


class CoveragePart(BaseModel):
    score: float
    points: float
    max: float
    explored: int
    total: int
    weak: list[str]
    missing: list[str]


class QualityPenalty(BaseModel):
    key: str
    label: str
    points: float


class InteractionPart(BaseModel):
    score: float
    penalties: list[QualityPenalty]


class QualityParts(BaseModel):
    questions: QuestionsPart
    coverage: CoveragePart | None = None
    interaction: InteractionPart | None = None


class SpeakingStretch(BaseModel):
    ms: int
    start_ms: int


class SpeakingSegment(BaseModel):
    speaker: Literal["interviewer", "candidate"]
    start_ms: int
    end_ms: int
    turn_id: int | None = Field(
        default=None, description="Its first transcript turn, to open the transcript there."
    )


class QualityMetrics(BaseModel):
    interviewer_ms: int
    candidate_ms: int
    candidate_share: float | None
    longest_stretch: SpeakingStretch | None
    small_talk_ms: int
    small_talk_share: float | None
    small_talk_questions: int
    follow_ups: list[str] = Field(description="The questions that were followed up.")
    questions_by_kind: dict[str, int]
    job_questions: int
    planned_minutes: int | None
    actual_minutes: int | None
    actual_ms: int | None
    planned_ms: int | None
    segments: list[SpeakingSegment]


class QualityRequirement(BaseModel):
    id: str
    text: str
    priority: str


class InterviewQuality(BaseModel):
    """How the interview itself was run (F10). About the interview, not the
    candidate."""

    status: Literal["checked"]
    checked_at: datetime
    score: float | None = Field(description="Average of the three parts, 0-100.")
    label: Literal["good", "needs_improvement", "poor"] | None = Field(
        description="good 70+, needs_improvement 50-69, poor below 50."
    )
    parts: QualityParts
    metrics: QualityMetrics
    findings: list[QualityFinding]
    recommendations: QualityRecommendations
    explored: list[str] = Field(description="The requirements its questions explored.")
    requirements: list[QualityRequirement]


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
        default=None,
        description="Average of the assessed interview dimensions (F9); for an interview "
        "evaluated before F9, the average score of the evaluated answers.",
    )
    interview_dimensions: InterviewDimensions | None = Field(
        default=None,
        description="The six interview performance dimensions; empty for an interview "
        "evaluated before F9.",
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
    approved_by_name: str | None = None
    claim_checks: ClaimChecks | None = Field(
        default=None,
        description="CV claims compared with the interview (F8); empty for an interview "
        "evaluated before F8. They never change a score, the report or the decision.",
    )
    interview_quality: InterviewQuality | None = Field(
        default=None,
        description="How the interview was run (F10); empty for an interview evaluated "
        "before F10. It never changes a score, the report or the decision.",
    )
    decision: Literal["hire", "reject"] | None = Field(
        default=None, description="The interviewer's decision (F11), after approval."
    )
    feedback_status: str | None = Field(
        default=None, description="The candidate's feedback email; empty while not written."
    )
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
    interview_dimensions: InterviewDimensions | None = Field(
        default=None, description="Empty before the report, or for an interview before F9."
    )
    overall_score: float | None
    suitability: Literal["strong_fit", "possible_fit", "not_a_fit"] | None
    answers_evaluated: int = Field(description="Answers the interview score averages.")
    coverage: CoverageCounts | None
    coverage_map: list[CoverageEntry] | None = Field(
        default=None, description="Each requirement's coverage, for comparing candidates."
    )
    strengths: list[Claim] | None
    weaknesses: list[Claim] | None
    gaps: list[Claim] | None
    areas_to_verify: list[Claim] | None
    approved_at: datetime | None
    open_contradictions: int = Field(
        default=0, description="CV claim contradictions not marked checked or dismissed yet."
    )
    decision: Literal["hire", "reject"] | None = Field(
        default=None, description="The interviewer's decision, after the report is approved."
    )
    feedback_status: str | None = Field(
        default=None, description="The candidate's feedback email; empty while not written."
    )
    feedback_warnings: int = 0


class ApproveAllResult(BaseModel):
    approved: int = Field(description="Draft reports approved now.")
    skipped: int = Field(
        description="Drafts not waiting for review, for example being rewritten."
    )


class EvaluationActivity(BaseModel):
    """A job's interview evaluations: the one running, the last finished one
    and how many completed interviews are waiting. While a task runs, its
    result holds session_ids, current and failures (each with session_id
    and reason)."""

    running: TaskResponse | None
    last: TaskResponse | None
    waiting: int = Field(description="Completed interviews not evaluated yet.")


class ConsistencyTypical(BaseModel):
    minutes: float | None
    questions: float | None
    candidate_share: float | None


class ConsistencyRequirement(BaseModel):
    id: str
    text: str
    priority: str
    asked: int = Field(description="Interviews whose questions explored it.")
    total: int
    mostly_missed: bool = Field(description="Explored in fewer than half of the interviews.")


class ConsistencyFlag(BaseModel):
    kind: Literal["must_have_not_asked", "length", "questions", "speaking_share"]
    text: str
    requirement_id: str | None = None
    asked: int | None = None
    others: int | None = None
    value: float | None = None


class ConsistencyInterview(BaseModel):
    session_id: int
    candidate_name: str
    interview_at: datetime | None
    minutes: int | None
    questions: int
    candidate_share: float | None
    explored: list[str]
    quality_score: float | None
    quality_label: Literal["good", "needs_improvement", "poor"] | None
    flags: list[ConsistencyFlag]


class InterviewConsistency(BaseModel):
    """Were the job's candidates interviewed in a similar way (F10)? Worked
    out from the evaluated interviews with an interview quality check."""

    count: int = Field(description="Interviews compared.")
    min_interviews: int
    typical: ConsistencyTypical | None = Field(
        description="The middle values; empty with fewer than min_interviews."
    )
    requirements: list[ConsistencyRequirement]
    interviews: list[ConsistencyInterview] = Field(
        description="Most differences first, then by name."
    )
    differ: int = Field(description="Interviews with at least one flag.")
