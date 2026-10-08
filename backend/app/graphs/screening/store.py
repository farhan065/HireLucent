"""Database reads and writes for the CV Screening graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
"""

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Candidate, Job, ScreeningResult
from app.models.enums import CandidateStatus

# Candidates that may still need screening: new ones, and ones that failed.
TO_SCREEN = (CandidateStatus.APPLIED, CandidateStatus.SCREENING_FAILED)


def _waiting(job_id: int):
    """Candidates of a job with screening steps still to run. One that has a
    screening result has been through every step built so far."""
    return (
        select(Candidate)
        .outerjoin(ScreeningResult)
        .where(
            Candidate.job_id == job_id,
            Candidate.status.in_(TO_SCREEN),
            ScreeningResult.id.is_(None),
        )
    )


def load_cvs(job_id: int) -> list[dict]:
    """The CVs of a job that are waiting to be screened. A CV that was read
    and parsed before carries its text and facts, so it is not read again."""
    with SessionLocal() as db:
        cvs = []
        for candidate in db.scalars(_waiting(job_id).order_by(Candidate.id)):
            cv = {"candidate_id": candidate.id, "cv_path": candidate.cv_path}
            if candidate.cv_parsed:
                cv |= {
                    "text": candidate.cv_text,
                    "text_source": candidate.cv_text_source,
                    "parsed": candidate.cv_parsed,
                }
            cvs.append(cv)
        return cvs


def count_to_screen(job_id: int) -> int:
    """How many CVs of a job are waiting to be screened."""
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(_waiting(job_id).subquery()))


def load_requirements(job_id: int) -> dict:
    """The job's requirements checklist, the same for every CV."""
    with SessionLocal() as db:
        return db.get(Job, job_id).requirements


def save_cv(candidate_id: int, text: str, source: str, parsed: dict) -> None:
    """Keep the text and the structured facts read from a CV."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.cv_text = text
        candidate.cv_text_source = source
        candidate.cv_parsed = parsed
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


def save_exclusion(candidate_id: int, reasons: list[str]) -> None:
    """Exclude a candidate who misses a must-have, with every reason."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.status = CandidateStatus.EXCLUDED
        candidate.screening_error = None
        _result(db, candidate_id).excluded_reason = "\n".join(reasons)
        db.commit()


def save_passed(candidate_id: int) -> None:
    """Record that a candidate met the must-haves. Matching and scoring
    fill in the rest of the result in later steps."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.screening_error = None
        candidate.status = CandidateStatus.APPLIED
        _result(db, candidate_id).excluded_reason = None
        db.commit()


def _result(db, candidate_id: int) -> ScreeningResult:
    result = db.scalar(
        select(ScreeningResult).where(ScreeningResult.candidate_id == candidate_id)
    )
    if result is None:
        result = ScreeningResult(candidate_id=candidate_id)
        db.add(result)
    return result
