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
from app.models.enums import UserRole
from app.schemas.job import JobRequirements, RequirementItem, ScoringWeights
from app.services import job_service

logger = get_logger(__name__)

SAMPLE_JOB_TITLE = "Backend Engineer (Python)"
SAMPLE_JD_TEXT = (
    "We are hiring a Backend Engineer to build and maintain REST APIs in "
    "Python. You will design database schemas, write tested services and "
    "work with containerised deployments."
)
SAMPLE_REQUIREMENTS = JobRequirements(
    min_experience_years=2,
    items=[
        RequirementItem(
            id="R1",
            text="Python web development",
            category="technical_skills",
            priority="must_have",
            keywords=["python", "django", "flask", "fastapi"],
        ),
        RequirementItem(
            id="R2",
            text="REST API design",
            category="technical_skills",
            priority="must_have",
            keywords=["rest", "api"],
        ),
        RequirementItem(
            id="R3",
            text="SQL databases",
            category="technical_skills",
            priority="must_have",
            keywords=["sql", "postgresql", "mysql"],
        ),
        RequirementItem(
            id="R4",
            text="Docker",
            category="technical_skills",
            priority="preferred",
            keywords=["docker", "container"],
        ),
        RequirementItem(
            id="R5",
            text="Hands-on backend development experience",
            category="experience",
            priority="preferred",
            keywords=["backend", "server-side"],
        ),
        RequirementItem(
            id="R6",
            text="BSc in Computer Science or a related field",
            category="qualifications",
            priority="preferred",
            keywords=["bsc", "bachelor", "computer science"],
        ),
    ],
)
SAMPLE_WEIGHTS = ScoringWeights(technical_skills=0.5, experience=0.3, qualifications=0.2)


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
    job = db.scalar(select(Job).where(Job.title == SAMPLE_JOB_TITLE))
    if job is not None:
        log_event(logger, "seed_job_exists", job_id=job.id)
        return

    job = job_service.create_job(
        db,
        title=SAMPLE_JOB_TITLE,
        jd_text=SAMPLE_JD_TEXT,
        requirements=SAMPLE_REQUIREMENTS,
        scoring_weights=SAMPLE_WEIGHTS,
        created_by=owner.id,
    )
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