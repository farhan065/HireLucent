"""Allowed values for status and type columns."""

from enum import StrEnum


class UserRole(StrEnum):
    """The two roles. Only interviewers have a row in the users table."""

    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class JobStatus(StrEnum):
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CandidateSource(StrEnum):
    EMAIL = "email"
    FORM = "form"


class CandidateStatus(StrEnum):
    APPLIED = "applied"
    SCREENING_FAILED = "screening_failed"
    EXCLUDED = "excluded"
    SCREENED = "screened"
    SHORTLISTED = "shortlisted"
    SELECTED = "selected"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    ASSESSED = "assessed"


class Decision(StrEnum):
    HIRE = "hire"
    HOLD = "hold"
    REJECT = "reject"


class SessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Speaker(StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class AssessmentStatus(StrEnum):
    ANALYSED = "analysed"
    DRAFT = "draft"
    APPROVED = "approved"


class DocumentType(StrEnum):
    JD_TEMPLATE = "jd_template"
    REFERENCE = "reference"
    QUESTIONS = "questions"


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ConversationStage(StrEnum):
    DESCRIBING = "describing"
    REVIEWING_DESCRIPTION = "reviewing_description"
    CONFIRMING_REQUIREMENTS = "confirming_requirements"
    SAVED = "saved"
