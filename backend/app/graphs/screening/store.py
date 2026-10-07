"""Database reads and writes for the CV Screening graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Candidate
from app.models.enums import CandidateStatus

# Candidates that still need screening: new ones, and ones that failed before.
TO_SCREEN = (CandidateStatus.APPLIED, CandidateStatus.SCREENING_FAILED)


def load_cvs(job_id: int) -> list[dict]:
    """The CVs of a job that are waiting to be screened."""
    with SessionLocal() as db:
        rows = db.execute(
            select(Candidate.id, Candidate.cv_path)
            .where(Candidate.job_id == job_id, Candidate.status.in_(TO_SCREEN))
            .order_by(Candidate.id)
        )
        return [{"candidate_id": row.id, "cv_path": row.cv_path} for row in rows]


def save_text(candidate_id: int, text: str, source: str) -> None:
    """Keep the text read from a CV. Screening continues from it."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.cv_text = text
        candidate.cv_text_source = source
        candidate.screening_error = None
        candidate.status = CandidateStatus.APPLIED
        db.commit()


def save_failure(candidate_id: int, reason: str) -> None:
    """Mark a CV that could not be processed, with the reason."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.status = CandidateStatus.SCREENING_FAILED
        candidate.screening_error = reason[:255]
        db.commit()
