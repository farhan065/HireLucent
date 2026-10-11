"""JobService: creating, reading, updating and archiving job profiles."""

import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.models import Candidate, Job, ScreeningResult
from app.models.enums import CandidateStatus, JobStatus
from app.schemas.job import JobRequirements, ScoringWeights
from app.services import task_service

logger = get_logger(__name__)

JOB_CODE_PREFIX = "HL"
# Statuses that only exist because of screening. They go back to "applied"
# when the requirements change, so the candidate is screened again.
SCREENED_STATUSES = (
    CandidateStatus.SCREENED,
    CandidateStatus.EXCLUDED,
    CandidateStatus.SHORTLISTED,
)


def build_job_code(title: str, existing_codes: list[str]) -> str:
    """Build a code such as HL-BE-01 from the title and the codes in use.

    Initials come from the first two words of the title. The number is one
    more than the highest number already used with the same initials.
    """
    words = re.findall(r"[A-Za-z]+", title)
    if len(words) >= 2:
        initials = words[0][0] + words[1][0]
    elif words:
        initials = words[0][:2]
    else:
        initials = "JB"
    start = f"{JOB_CODE_PREFIX}-{initials.upper()}-"

    numbers = [
        int(code[len(start) :])
        for code in existing_codes
        if code.startswith(start) and code[len(start) :].isdigit()
    ]
    return f"{start}{max(numbers, default=0) + 1:02d}"


def create_job(
    db: Session,
    title: str,
    jd_text: str,
    requirements: JobRequirements,
    scoring_weights: ScoringWeights,
    created_by: int,
) -> Job:
    """Save an approved job. Called by the Recruiter Agent after approval."""
    # The job_code column is unique in the database. If two jobs are saved at
    # the same moment with the same code, the second save fails and we try
    # again with the next number.
    for _ in range(3):
        existing_codes = list(db.scalars(select(Job.job_code)))
        job = Job(
            job_code=build_job_code(title, existing_codes),
            title=title,
            jd_text=jd_text,
            requirements=requirements.model_dump(),
            scoring_weights=scoring_weights.model_dump(),
            status=JobStatus.APPROVED,
            created_by=created_by,
        )
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        log_event(logger, "job_created", job_id=job.id)
        return job
    raise ConflictError("The job could not be saved. Please try again.")


def list_jobs(db: Session) -> list[Job]:
    """All jobs, newest first, each with its candidate counts attached."""
    jobs = list(db.scalars(select(Job).order_by(Job.created_at.desc())))
    counts = db.execute(
        select(Candidate.job_id, Candidate.status, func.count()).group_by(
            Candidate.job_id, Candidate.status
        )
    )
    counts_by_job: dict[int, dict[str, int]] = {}
    for job_id, status, count in counts:
        counts_by_job.setdefault(job_id, {})[status] = count
    for job in jobs:
        job.candidate_counts = counts_by_job.get(job.id, {})
    return jobs


def get_job(db: Session, job_id: int) -> Job:
    """One job with its candidate counts and how many have been screened,
    or a 404 error."""
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError("This job does not exist.")
    counts = db.execute(
        select(Candidate.status, func.count())
        .where(Candidate.job_id == job_id)
        .group_by(Candidate.status)
    )
    job.candidate_counts = {status: count for status, count in counts}
    job.screened_count = screened_count(db, job_id)
    return job


def screened_count(db: Session, job_id: int) -> int:
    """How many of the job's candidates have screening results."""
    return db.scalar(
        select(func.count())
        .select_from(ScreeningResult)
        .join(Candidate)
        .where(Candidate.job_id == job_id)
    )


def update_profile(
    db: Session,
    job_id: int,
    requirements: JobRequirements,
    scoring_weights: ScoringWeights,
) -> Job:
    """Change the requirements and weights.

    Screening results made with the old rules are cleared, so every
    candidate of the job is screened again with the same rules. Refused
    while a fetch or a screening is running for the job.
    """
    get_job(db, job_id)
    task_service.ensure_idle(db, job_id)
    job = db.get(Job, job_id)
    job.requirements = requirements.model_dump()
    job.scoring_weights = scoring_weights.model_dump()
    reset = reset_screening(db, job_id)
    db.commit()
    log_event(logger, "job_profile_updated", job_id=job.id, screening_reset=reset)
    return get_job(db, job_id)


def reset_screening(db: Session, job_id: int) -> int:
    """Clear the job's screening results and put screened, excluded and
    shortlisted candidates back to "applied", ready to screen again.

    The text and facts read from each CV are kept, so screening starts at
    the must-have check without reading the CVs again. Candidates whose CV
    could not be read keep that status; screening retries them anyway.
    Returns how many candidates had results. The caller commits.
    """
    candidate_ids = select(Candidate.id).where(Candidate.job_id == job_id)
    reset = db.execute(
        delete(ScreeningResult).where(ScreeningResult.candidate_id.in_(candidate_ids))
    ).rowcount
    for candidate in db.scalars(
        select(Candidate).where(
            Candidate.job_id == job_id, Candidate.status.in_(SCREENED_STATUSES)
        )
    ):
        candidate.status = CandidateStatus.APPLIED
    return reset


def mark_published(
    db: Session, job_id: int, form_id: str, form_url: str, post_url: str
) -> Job:
    """Record the application form and the public post of a published job."""
    job = get_job(db, job_id)
    job.form_id = form_id
    job.form_url = form_url
    job.post_url = post_url
    job.status = JobStatus.PUBLISHED
    job.published_at = datetime.now(UTC)
    db.commit()
    log_event(logger, "job_published", job_id=job.id)
    return get_job(db, job_id)


def form_is_used(db: Session, form_id: str, except_job_id: int) -> bool:
    """True if another job already collects its applications from this form."""
    other = db.scalar(
        select(Job.id).where(Job.form_id == form_id, Job.id != except_job_id).limit(1)
    )
    return other is not None


def archive_job(db: Session, job_id: int) -> Job:
    """Mark a job as archived. Its data is kept."""
    job = get_job(db, job_id)
    job.status = JobStatus.ARCHIVED
    db.commit()
    log_event(logger, "job_archived", job_id=job.id)
    return get_job(db, job_id)