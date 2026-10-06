"""Database models. Importing this package registers every table."""

from app.models.assessment import Assessment
from app.models.base import Base
from app.models.candidate import Candidate, ScreeningResult
from app.models.document import Document
from app.models.interview import InterviewSession, TranscriptTurn
from app.models.job import Job
from app.models.task import Task
from app.models.user import User

__all__ = [
    "Assessment",
    "Base",
    "Candidate",
    "Document",
    "InterviewSession",
    "Job",
    "ScreeningResult",
    "Task",
    "TranscriptTurn",
    "User",
]