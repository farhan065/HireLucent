"""Database models. Importing this package registers every table."""

from app.models.assessment import Assessment
from app.models.base import Base
from app.models.candidate import Candidate, RemovedApplication, ScreeningResult
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.feedback import CandidateFeedback
from app.models.interview import InterviewSession, TranscriptTurn
from app.models.job import Job
from app.models.task import Task
from app.models.user import User

__all__ = [
    "Assessment",
    "Base",
    "Candidate",
    "CandidateFeedback",
    "Conversation",
    "Document",
    "InterviewSession",
    "Job",
    "RemovedApplication",
    "ScreeningResult",
    "Task",
    "TranscriptTurn",
    "User",
]
