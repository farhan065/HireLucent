"""Job profile endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.db.session import get_db
from app.models import Job
from app.graphs.screening import store as screening_store
from app.schemas.error import ErrorResponse
from app.schemas.candidate import ShortlistCount, ShortlistRule
from app.schemas.job import JobDetail, JobProfileUpdate, JobSummary
from app.schemas.task import JobActivity
from app.services import (
    intake_service,
    job_deletion,
    job_service,
    screening_service,
    shortlist_service,
    task_service,
)

router = APIRouter(
    prefix="/jobs", tags=["Jobs"], dependencies=[Depends(require_interviewer)]
)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}


@router.get("", response_model=list[JobSummary], summary="List all jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    """Jobs, newest first, with the number of candidates in each status."""
    return job_service.list_jobs(db)


@router.get(
    "/{job_id}", response_model=JobDetail, summary="Get one job", responses=NOT_FOUND
)
def read_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    return job_service.get_job(db, job_id)


@router.put(
    "/{job_id}/profile",
    response_model=JobDetail,
    summary="Change a job's requirements and scoring weights",
    responses={
        **NOT_FOUND,
        409: {
            "model": ErrorResponse,
            "description": "A fetch or screening is running, or the job has interviews",
        },
    },
)
def update_job_profile(
    job_id: int, payload: JobProfileUpdate, db: Session = Depends(get_db)
) -> Job:
    """Screening results made with the old rules are cleared, so every
    candidate is screened again with the new ones. The public post and the
    description do not change. Refused once the job has interviews, so every
    interviewed candidate keeps scores made with the same rules."""
    return job_service.update_profile(
        db, job_id, payload.requirements, payload.scoring_weights
    )


@router.post(
    "/{job_id}/archive",
    response_model=JobDetail,
    summary="Archive a job",
    responses=NOT_FOUND,
)
def archive_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    return job_service.archive_job(db, job_id)


@router.get(
    "/{job_id}/activity",
    response_model=JobActivity,
    summary="See what is running for a job and how its last runs ended",
    responses=NOT_FOUND,
)
def read_job_activity(job_id: int, db: Session = Depends(get_db)) -> JobActivity:
    """Lets the screen show progress again after a page reload."""
    job_service.get_job(db, job_id)
    return JobActivity(
        running=task_service.running_task(db, job_id, exclude=task_service.NOT_CV_WORK),
        last_intake=task_service.last_finished(db, job_id, intake_service.TASK_KIND),
        last_screening=task_service.last_finished(
            db, job_id, screening_service.TASK_KIND
        ),
        ready_to_screen=screening_store.count_to_screen(job_id),
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job and everything stored for it",
    responses={
        **NOT_FOUND,
        409: {
            "model": ErrorResponse,
            "description": "A task is running, or the job has upcoming interviews",
        },
    },
)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> None:
    """Removes the job, its candidates, their CV files and screening data,
    and its conversation. The public post and the application form are not
    touched. This cannot be undone."""
    job_deletion.delete_job(db, job_id)


@router.post(
    "/{job_id}/shortlist",
    response_model=ShortlistCount,
    summary="Shortlist the top N candidates, or everyone above a final score",
    responses=NOT_FOUND,
)
def apply_shortlist_rule(
    job_id: int, payload: ShortlistRule, db: Session = Depends(get_db)
) -> ShortlistCount:
    """Adds to the shortlist; nobody already on it is removed."""
    count = shortlist_service.shortlist_by_rule(db, job_id, payload.top, payload.min_score)
    return ShortlistCount(shortlisted=count)


@router.delete(
    "/{job_id}/shortlist",
    response_model=ShortlistCount,
    summary="Take everyone off the job's shortlist",
    responses=NOT_FOUND,
)
def clear_shortlist(job_id: int, db: Session = Depends(get_db)) -> ShortlistCount:
    return ShortlistCount(shortlisted=shortlist_service.clear(db, job_id))
