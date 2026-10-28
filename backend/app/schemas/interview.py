"""Schemas for interview sessions."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.services.interview_emails import clean_message

# The interviewer's own message paragraph in the email: plain text, not
# empty, at most 1500 characters.
EmailMessage = Annotated[str, AfterValidator(clean_message)]
MESSAGE_FIELD = Field(
    default=None,
    description="The interviewer's own message paragraph. Leave out for the default.",
)


class IdentityCheck(BaseModel):
    """Whether the person who joined looks like the invited candidate (F7).
    Interviewer-only; it never stops the candidate from joining."""

    result: Literal["pending", "verified", "low", "very_low", "other_applicant", "not_checked"]
    score: float | None = Field(
        default=None, description="Match with the invited candidate's photo, -1 to 1."
    )
    other_candidate_name: str | None = Field(
        default=None, description="The other applicant of the job the photo matched best."
    )
    other_score: float | None = None
    reason: str | None = Field(default=None, description="Why it was not checked.")
    checked_at: datetime | None = None


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
    candidate_waiting: bool = Field(
        default=False, description="The candidate is in the waiting room now."
    )
    assessment_status: str | None = Field(
        default=None,
        description="analysed, draft or approved; empty until the interview is evaluated.",
    )
    identity: IdentityCheck | None = Field(
        default=None,
        description="The identity check (F7). Empty for interviews scheduled before F7.",
    )


class InterviewRoomInfo(BaseModel):
    """What the interview room shows about its interview."""

    interview: InterviewSessionSummary
    job_id: int
    job_title: str
    job_code: str


class InterviewTime(BaseModel):
    """A start and end time, each with its time zone."""

    start: AwareDatetime
    end: AwareDatetime


class ScheduleSlot(InterviewTime):
    candidate_id: int


class ScheduleRequest(BaseModel):
    """Interviews to schedule for a job, at most 20 at once, with one
    message for every candidate."""

    interviews: list[ScheduleSlot] = Field(min_length=1, max_length=20)
    message: EmailMessage | None = MESSAGE_FIELD

    @field_validator("interviews")
    @classmethod
    def one_interview_per_candidate(cls, interviews: list[ScheduleSlot]) -> list[ScheduleSlot]:
        ids = [slot.candidate_id for slot in interviews]
        if len(ids) != len(set(ids)):
            raise ValueError("Each candidate can be scheduled only once at a time.")
        return interviews


class RescheduleRequest(InterviewTime):
    """An interview's new time, with an optional message."""

    message: EmailMessage | None = MESSAGE_FIELD


class CancelRequest(BaseModel):
    message: EmailMessage | None = MESSAGE_FIELD


class NewPinRequest(BaseModel):
    """Send the candidate a new link and PIN, with an optional message."""

    message: EmailMessage | None = MESSAGE_FIELD


class EmailPreviewRequest(InterviewTime):
    """The email one candidate would get. For a cancellation, the times are
    the interview's current ones."""

    kind: Literal["invitation", "moved", "cancelled", "new_pin"]
    candidate_id: int
    message: EmailMessage | None = MESSAGE_FIELD


class EmailPreview(BaseModel):
    """An email as the candidate will see it, with "[private link]" and
    "[private PIN]" in place of their link and PIN."""

    subject: str
    text: str
    message: str = Field(description="The message paragraph used in the email.")
    default_message: str


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


class InterviewRules(BaseModel):
    """The scheduling rules, in minutes."""

    min_notice_minutes: int
    join_opens_minutes_before: int
    min_length_minutes: int
    max_length_minutes: int


class SuggestedQuestion(BaseModel):
    """A question the AI suggested for the candidate in this interview."""

    id: int
    requirement_id: str | None = Field(description="The requirement it checks, such as R2.")
    requirement: str | None = Field(description="That requirement's text.")
    reason: Literal["partly_met", "not_in_cv", "cv_claim"] = Field(
        description="Partly met, not shown in the CV, or a claim the CV makes."
    )
    question: str
    why: str
    asked: bool


class QuestionAsked(BaseModel):
    asked: bool


class InterviewChatMessage(BaseModel):
    """One message in the interview room's chat with the AI Agent."""

    role: Literal["interviewer", "agent"]
    text: str
    from_question_bank: bool = Field(
        default=False, description="The answer quotes questions from the question bank."
    )
    failed: bool = Field(
        default=False, description="The AI Agent could not answer; the text says why."
    )


class InterviewChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
