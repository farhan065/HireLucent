"""Load starting data into the database.

Usage (inside the backend container):
    python -m scripts.seed                 # create the interviewer account
    python -m scripts.seed --sample-data   # also create a sample job

Running it again is safe: rows that already exist are left unchanged.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Job, User
from app.models.enums import JobStatus, UserRole

logger = get_logger(__name__)

SAMPLE_JOB_CODE = "HL-BE-01"
SAMPLE_JOB = {
    "title": "Backend Engineer (Python)",
    "jd_text": (
        "We are hiring a Backend Engineer to build and maintain REST APIs in "
        "Python. You will design database schemas, write tested services and "
        "work with containerised deployments."
    ),
    "requirements": {
        "must_haves": ["Python web development", "REST API design", "SQL databases"],
        "preferred": ["Docker", "FastAPI", "Automated testing"],
        "min_experience_years": 2,
        "qualifications": ["BSc in Computer Science or a related field"],
    },
    "scoring_weights": {
        "technical_skills": 0.5,
        "experience": 0.3,
        "qualifications": 0.2,
    },
}


def seed_interviewer(db: Session, settings: Settings) -> User | None:
    """Create the first interviewer account from the SEED_* settings."""
    email = settings.seed_interviewer_email
    password = settings.seed_interviewer_password
    if not email or not password:
        log_event(logger, "seed_interviewer_skipped", reason="settings_missing")
        return None

    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        log_event(logger, "seed_interviewer_exists", user_id=user.id)
        return user

    user = User(
        email=email,
        full_name=settings.seed_interviewer_name,
        password_hash=hash_password(password),
        role=UserRole.INTERVIEWER,
    )
    db.add(user)
    db.commit()
    log_event(logger, "seed_interviewer_created", user_id=user.id)
    return user


def seed_sample_job(db: Session, owner: User) -> None:
    """Create one sample job so intake and screening can be tried out."""
    job = db.scalar(select(Job).where(Job.job_code == SAMPLE_JOB_CODE))
    if job is not None:
        log_event(logger, "seed_job_exists", job_id=job.id)
        return

    job = Job(
        job_code=SAMPLE_JOB_CODE,
        status=JobStatus.APPROVED,
        created_by=owner.id,
        **SAMPLE_JOB,
    )
    db.add(job)
    db.commit()
    log_event(logger, "seed_job_created", job_id=job.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load starting data.")
    parser.add_argument(
        "--sample-data", action="store_true", help="also create a sample job"
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    with SessionLocal() as db:
        user = seed_interviewer(db, settings)
        if args.sample_data and user is not None:
            seed_sample_job(db, user)


if __name__ == "__main__":
    main()