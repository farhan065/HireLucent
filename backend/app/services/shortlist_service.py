"""ShortlistService: the interviewer's shortlist of scored candidates.

Screening never shortlists anyone. The interviewer adds candidates one by
one or by a rule (top N, or a minimum final score), and can remove them at
any time. Shortlisting changes only the status, never a score or a rank.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.models import Candidate, ScreeningResult
from app.models.enums import CandidateStatus
from app.services import job_service

logger = get_logger(__name__)

NOT_SCORED = "Only candidates with a final score can be shortlisted."
SCORED = (CandidateStatus.SCREENED, CandidateStatus.SHORTLISTED)


def set_shortlisted(db: Session, candidate_id: int, shortlisted: bool) -> Candidate:
    """Add one candidate to the shortlist, or remove them from it."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError("This candidate does not exist.")
    if candidate.status not in SCORED:
        raise ConflictError(NOT_SCORED)
    candidate.status = CandidateStatus.SHORTLISTED if shortlisted else CandidateStatus.SCREENED
    db.commit()
    log_event(logger, "shortlist_changed", candidate_id=candidate_id, shortlisted=shortlisted)
    return candidate


def shortlist_by_rule(
    db: Session, job_id: int, top: int | None = None, min_score: float | None = None
) -> int:
    """Shortlist the top N candidates of the final ranking, or everyone with
    at least a given final score. Candidates already shortlisted stay on it.
    Returns how many are on the shortlist afterwards."""
    job_service.get_job(db, job_id)
    query = (
        select(Candidate)
        .join(ScreeningResult)
        .where(Candidate.job_id == job_id, Candidate.status.in_(SCORED))
        .order_by(ScreeningResult.final_rank)
    )
    if min_score is not None:
        query = query.where(ScreeningResult.final_score >= min_score)
    if top is not None:
        query = query.limit(top)
    for candidate in db.scalars(query):
        candidate.status = CandidateStatus.SHORTLISTED
    db.commit()
    count = _count(db, job_id)
    log_event(logger, "shortlist_applied", job_id=job_id, shortlisted=count)
    return count


def clear(db: Session, job_id: int) -> int:
    """Take everyone off the job's shortlist. Returns 0."""
    job_service.get_job(db, job_id)
    for candidate in db.scalars(
        select(Candidate).where(
            Candidate.job_id == job_id, Candidate.status == CandidateStatus.SHORTLISTED
        )
    ):
        candidate.status = CandidateStatus.SCREENED
    db.commit()
    log_event(logger, "shortlist_cleared", job_id=job_id)
    return 0


def _count(db: Session, job_id: int) -> int:
    return len(
        db.scalars(
            select(Candidate.id).where(
                Candidate.job_id == job_id, Candidate.status == CandidateStatus.SHORTLISTED
            )
        ).all()
    )
