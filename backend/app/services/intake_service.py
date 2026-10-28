"""IntakeService: collects the CVs submitted through a job's application form.

No AI is used here. A fetch reads the form's responses, downloads each new
CV from Google Drive, checks it, stores it and creates the candidate.
Running it again later collects only what arrived since.
"""

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path, PurePath
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.db.session import SessionLocal
from app.models import Candidate, Job, RemovedApplication, Task
from app.models.enums import CandidateSource, CandidateStatus, FaceStatus, JobStatus
from app.services import face_service, google_drive, google_forms, job_service, task_service
from app.services.google_forms import FormResponse
from app.services.task_service import TaskProgress
from app.services.text_extraction import UnsupportedFileError, check_file

logger = get_logger(__name__)

TASK_KIND = "cv_intake"
CV_EXTENSIONS = {".pdf", ".docx"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PHOTO_FOLDER = "photos"
NOT_PUBLISHED_MESSAGE = "Publish the job before fetching CVs."
UNKNOWN_NAME = "Unknown applicant"
DOWNLOAD_FAILED = "The CV could not be downloaded."
CV_MISSING = "The CV file is no longer stored. Fetch the CVs again."
NO_PHOTO = "This candidate has no application photo."
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# How long a count of waiting applications is reused before Google is asked
# again, so reloading the dashboard does not call Google every time.
WAITING_CACHE_SECONDS = 120
_waiting_cache: dict[int, tuple[float, int]] = {}


def start_intake(
    db: Session, background_tasks: BackgroundTasks, job_id: int, user_id: int
) -> Task:
    """Start fetching a job's CVs in the background and return the task."""
    job = _published_job(db, job_id)
    task_service.ensure_idle(db, job_id, exclude=task_service.NOT_CV_WORK)
    form_id = job.form_id
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_intake(job_id, form_id, progress),
        job_id=job_id,
    )


def run_intake(job_id: int, form_id: str, progress: TaskProgress) -> dict:
    """Collect every new application. Returns the counts, and for each
    application that could not be collected, who applied and why."""
    responses = google_forms.list_responses(form_id)
    with SessionLocal() as db:
        applied = db.execute(
            select(Candidate.source_ref, Candidate.email).where(
                Candidate.job_id == job_id
            )
        ).all()
        known_refs = {ref for ref, _ in applied}
        known_emails = {email for _, email in applied}
        # Applications whose candidate was deleted are never collected again.
        removed = set(
            db.scalars(
                select(RemovedApplication.response_id).where(
                    RemovedApplication.job_id == job_id
                )
            )
        )
        new = [
            item
            for item in responses
            if item.response_id not in known_refs and item.response_id not in removed
        ]
        counts = {
            "collected": 0,
            "duplicates": 0,
            "failed": 0,
            "already_collected": len(responses) - len(new),
        }
        failed_items = []

        for index, response in enumerate(new, start=1):
            progress.update(index - 1, len(new), f"Collecting CV {index} of {len(new)}")
            outcome, reason = _collect(db, job_id, response, known_emails)
            counts[outcome] += 1
            if reason:
                failed_items.append(
                    {
                        "name": response.full_name[:255] or UNKNOWN_NAME,
                        "email": response.email[:255],
                        "reason": reason,
                    }
                )

        db.get(Job, job_id).responses_seen = len(responses)
        db.commit()

    _waiting_cache.pop(job_id, None)
    progress.update(len(new), len(new), "Finished")
    # Only the counts are logged. The names stay in the database.
    log_event(logger, "cv_intake_finished", job_id=job_id, **counts)
    return {**counts, "failed_items": failed_items}


def _collect(
    db: Session, job_id: int, response: FormResponse, known_emails: set[str]
) -> tuple[str, str | None]:
    """Collect one application. Returns collected, duplicates or failed,
    and for a failure the reason in words that are safe to show."""
    if response.email in known_emails:
        return "duplicates", None
    face: dict = {}
    try:
        extension, content = read_cv(response)
        path = _store(job_id, extension, content)
        face = enrol_face(job_id, response)
        db.add(
            Candidate(
                job_id=job_id,
                full_name=response.full_name[:255] or UNKNOWN_NAME,
                email=response.email,
                source=CandidateSource.FORM,
                source_ref=response.response_id,
                cv_path=str(path),
                status=CandidateStatus.APPLIED,
                **face,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if face.get("photo_path"):
            Path(face["photo_path"]).unlink(missing_ok=True)
        # Only the kind of problem is logged, never the applicant's details.
        log_event(
            logger,
            "cv_intake_item_failed",
            level=logging.WARNING,
            job_id=job_id,
            error_type=type(exc).__name__,
        )
        return "failed", exc.message if isinstance(exc, AppError) else DOWNLOAD_FAILED
    known_emails.add(response.email)
    return "collected", None


def read_cv(response: FormResponse) -> tuple[str, bytes]:
    """Check an application and download its CV. Returns (extension, content)."""
    if not _EMAIL.match(response.email):
        raise UnsupportedFileError("The application has no valid email address.")
    if not response.file_id:
        raise UnsupportedFileError("The application has no CV attached.")
    if PurePath(response.file_name).suffix.lower() not in CV_EXTENSIONS:
        raise UnsupportedFileError("A CV must be a PDF or DOCX file.")

    max_mb = get_settings().max_upload_mb
    content = google_drive.download_file(response.file_id, max_mb)
    return check_file(response.file_name, content, max_mb), content


def enrol_face(job_id: int, response: FormResponse) -> dict:
    """The candidate's photo and face code from their application (F7), as
    candidate columns. A photo problem never stops the application: the
    face status says what went wrong. Without consent nothing is read."""
    if not response.consent:
        return {"face_status": FaceStatus.NO_CONSENT}
    consent = {"face_consent_at": response.submitted_at or datetime.now(timezone.utc)}
    if not response.photo_file_id:
        return {**consent, "face_status": FaceStatus.NO_PHOTO}
    check = _check_photo(response)
    if check.problem:
        log_event(
            logger,
            "face_photo_unusable",
            level=logging.WARNING,
            job_id=job_id,
            problem=check.problem,
        )
        return {
            **consent,
            "face_status": FaceStatus.PHOTO_UNUSABLE,
            "face_problem": check.problem,
        }
    photo_path = _store_photo(job_id, face_service.jpeg_for_storage(check.image))
    log_event(logger, "face_enrolled", job_id=job_id)
    return {
        **consent,
        "face_status": FaceStatus.ENROLLED,
        "face_code": check.code,
        "photo_path": str(photo_path),
    }


def _check_photo(response: FormResponse) -> face_service.FaceCheck:
    """Download the photo and check it in memory. The original file is
    never written; only a re-saved JPEG copy is kept, once it is usable."""
    if PurePath(response.photo_file_name).suffix.lower() not in PHOTO_EXTENSIONS:
        return face_service.FaceCheck(problem=face_service.NOT_AN_IMAGE)
    try:
        content = google_drive.download_file(response.photo_file_id, get_settings().max_photo_mb)
    except AppError:
        return face_service.FaceCheck(problem=face_service.NOT_DOWNLOADED)
    try:
        return face_service.check_photo(content)
    except Exception as exc:
        log_event(
            logger, "face_check_failed", level=logging.WARNING, error_type=type(exc).__name__
        )
        return face_service.FaceCheck(problem=face_service.CHECK_FAILED)


def _store_photo(job_id: int, content: bytes) -> Path:
    """Save the photo under a random name, next to the job's CVs, so it is
    removed with the job."""
    folder = Path(get_settings().cv_storage_dir) / str(job_id) / PHOTO_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}.jpg"
    path.write_bytes(content)
    return path


def photo_file(db: Session, candidate_id: int) -> Path:
    """Where a candidate's application photo is stored, or a 404 error."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError("This candidate does not exist.")
    if not candidate.photo_path or not Path(candidate.photo_path).is_file():
        raise NotFoundError(NO_PHOTO)
    return Path(candidate.photo_path)


def _store(job_id: int, extension: str, content: bytes) -> Path:
    """Save a CV under a random name, so the file name holds no personal data."""
    folder = Path(get_settings().cv_storage_dir) / str(job_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}{extension}"
    path.write_bytes(content)
    return path


def waiting_count(db: Session, job_id: int) -> int | None:
    """How many applications have arrived since the last fetch.

    Only counts; nothing is downloaded. Returns None when the job is not
    published or Google cannot be asked, so the screen simply shows nothing.
    """
    job = job_service.get_job(db, job_id)
    if job.status != JobStatus.PUBLISHED or not job.form_id:
        return None

    cached = _waiting_cache.get(job_id)
    if cached and time.monotonic() - cached[0] < WAITING_CACHE_SECONDS:
        return cached[1]
    try:
        total = len(google_forms.list_responses(job.form_id))
    except AppError as exc:
        log_event(
            logger,
            "cv_waiting_count_unavailable",
            level=logging.WARNING,
            job_id=job_id,
            error_type=type(exc).__name__,
        )
        return None
    waiting = max(0, total - job.responses_seen)
    _waiting_cache[job_id] = (time.monotonic(), waiting)
    return waiting


def list_candidates(db: Session, job_id: int) -> list[Candidate]:
    """A job's candidates, most recent first."""
    job_service.get_job(db, job_id)
    return list(
        db.scalars(
            select(Candidate)
            .where(Candidate.job_id == job_id)
            .options(selectinload(Candidate.screening_result), selectinload(Candidate.feedback))
            .order_by(Candidate.created_at.desc(), Candidate.id.desc())
        )
    )


def cv_file(db: Session, candidate_id: int) -> Path:
    """Where a candidate's CV is stored, or a 404 error."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError("This candidate does not exist.")
    path = Path(candidate.cv_path)
    if not path.is_file():
        raise NotFoundError(CV_MISSING)
    return path


def _published_job(db: Session, job_id: int) -> Job:
    job = job_service.get_job(db, job_id)
    if job.status != JobStatus.PUBLISHED or not job.form_id:
        raise ConflictError(NOT_PUBLISHED_MESSAGE)
    return job
