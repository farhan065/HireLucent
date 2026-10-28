"""Database reads and writes for the Final Assessment graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Assessment, Candidate, InterviewSession, Job, TranscriptTurn
from app.models.enums import AssessmentStatus, CandidateStatus

# The report fields a draft holds, as named in the graph's state.
DRAFT_FIELDS = (
    "cv_score",
    "interview_dimensions",
    "interview_score",
    "overall_score",
    "strengths",
    "weaknesses",
    "gaps",
    "areas_to_verify",
)


def _cv_facts(candidate: Candidate | None) -> dict | None:
    if candidate is None or not candidate.cv_parsed:
        return None
    return {key: value for key, value in candidate.cv_parsed.items() if key != "contact"}


def load_results(session_id: int) -> dict | None:
    """The interview's Q&A analysis, the candidate's CV screening score, the
    job title, the candidate's turns (to check quotes) and the CV facts (for
    the claim check), or None when the interview has not been analysed."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        if assessment is None:
            return None
        session = db.get(InterviewSession, session_id)
        job = db.get(Job, session.job_id) if session else None
        candidate = db.get(Candidate, assessment.candidate_id)
        scores = candidate.scores if candidate else None
        turns = db.scalars(
            select(TranscriptTurn).where(TranscriptTurn.session_id == session_id)
        )
        return {
            "candidate_id": assessment.candidate_id,
            "job_title": job.title if job else "",
            "pairs": assessment.qa_evaluations,
            "coverage": assessment.coverage_map,
            "cv_score": scores["final_score"] if scores else None,
            # The CV facts for the claim check; contact details are kept
            # apart and never leave the backend.
            "cv": _cv_facts(candidate),
            "turns": [
                {"id": turn.id, "start_ms": turn.start_ms, "text": turn.text} for turn in turns
            ],
        }


def save_draft(session_id: int, values: dict) -> None:
    """Keep the report as a draft waiting for the interviewer's review."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        for field in DRAFT_FIELDS:
            setattr(assessment, field, values.get(field))
        assessment.report = values["summary"]
        assessment.status = AssessmentStatus.DRAFT
        assessment.approved_by = None
        assessment.approved_at = None
        db.commit()


def save_claim_checks(session_id: int, checks: dict) -> None:
    """Keep the CV claim check (F8) with the assessment. The report, its
    status and approval are not touched."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        if assessment is not None:
            assessment.claim_checks = checks
            db.commit()


def approve(session_id: int, reviewer_id: int) -> None:
    """Mark the report approved, with who approved it and when."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        assessment.status = AssessmentStatus.APPROVED
        assessment.approved_by = reviewer_id
        assessment.approved_at = datetime.now(timezone.utc)
        db.commit()


def mark_assessed(candidate_id: int) -> None:
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        if candidate is not None:
            candidate.status = CandidateStatus.ASSESSED
            db.commit()
