"""What the AI is told about one interview: the job and its requirements,
and the candidate's CV facts and screening results.

Only job-related facts go in. The candidate's email address, phone number
and links never do; the name is the only personal detail.
"""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import InterviewSession, Job
from app.services import session_service

# Parts of the read CV that are about reaching the person, not the job.
PRIVATE_FACTS = {"contact", "links", "email", "phone"}


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def describe(db: Session, session: InterviewSession) -> str:
    """The interview's job, requirements and candidate, as plain text."""
    job = db.get(Job, session.job_id)
    candidate = session.candidate
    requirements = (job.requirements or {}) if job else {}
    items = [
        {"id": item["id"], "text": item["text"], "priority": item["priority"]}
        for item in requirements.get("items", [])
    ]
    matches = [
        {
            "id": match["id"],
            "status": match["status"],
            "evidence": match.get("evidence"),
            "reason": match.get("reason"),
        }
        for match in candidate.requirement_matches or []
    ]
    facts = {
        key: value
        for key, value in (candidate.cv_parsed or {}).items()
        if key not in PRIVATE_FACTS
    }
    scores = candidate.scores or {}

    lines = [
        f"Job: {job.title} ({job.job_code})" if job else "Job: unknown",
        f"Minimum experience: {requirements.get('min_experience_years', 0)} years",
        f"Requirements: {_as_json(items)}",
        f"Candidate: {candidate.full_name}",
    ]
    if scores.get("final_score") is not None:
        lines.append(
            f"Final screening score: {round(scores['final_score'])} of 100, "
            f"rank {scores.get('final_rank') or 'not ranked'}"
        )
    if scores.get("summary"):
        lines.append(f"Screening summary: {scores['summary']}")
    lines.append(f"Requirement matches from screening: {_as_json(matches)}")
    lines.append(f"CV facts: {_as_json(facts)}")
    return "\n".join(lines)


def for_session(session_id: int) -> tuple[str, str]:
    """For the AI Agent, with its own database connection: the interview's
    details, and the job title that picks its question bank files."""
    with SessionLocal() as db:
        session = session_service.get_session(db, session_id)
        job = db.get(Job, session.job_id)
        return describe(db, session), job.title if job else ""
